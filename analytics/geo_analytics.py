#!/usr/bin/env python3
"""
GEO Analytics - Parse CloudFront logs and track access patterns.

Analyzes CloudFront access logs to track:
- Which Q&As are being accessed
- Which bots/LLMs are crawling content
- API usage patterns
- Traffic trends

Usage:
    from geo_analytics import GeoAnalytics

    analytics = GeoAnalytics(
        logs_bucket='rozzum-cloudfront-logs',
        logs_prefix='geo-logs/'
    )

    # Analyze logs for a domain
    stats = analytics.analyze_logs('rozz.site', days=7)

    # Generate report
    report = analytics.generate_report('rozz.site', days=7)
    print(report)
"""

import boto3
import os
import gzip
import csv
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter
from urllib.parse import unquote
import re
import hashlib
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

try:
    from utils.logtools import log_worker
except ImportError:
    def log_worker(domain, msg, worker="geo_analytics", level="INFO"):
        print(f"[{worker}] {msg}")

load_dotenv()


class GeoAnalytics:
    """Analytics for GEO content from CloudFront access logs."""

    SCANNER_REQUEST_THRESHOLD = 1000
    SCANNER_SUSPICIOUS_BOTS = {
        'cURL', 'Generic Bot', 'Generic Crawler', 'Generic Spider',
        'Python aiohttp', 'Other Bot', 'Unknown',
    }

    # ==========================================================================
    # BOT DETECTION PATTERNS
    # ==========================================================================
    # Pattern matching is case-insensitive against User-Agent strings.
    # Order matters: more specific patterns should come before generic ones.
    #
    # Reference sources:
    # - https://darkvisitors.com/agents
    # - https://github.com/monperrus/crawler-user-agents
    # - https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
    # ==========================================================================

    BOT_PATTERNS = {
        # ---------------------------------------------------------------------
        # ANTHROPIC / CLAUDE BOTS
        # Reference: https://darkvisitors.com/agents
        # ---------------------------------------------------------------------
        # ClaudeBot - Main crawler for training data collection
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)
        'claudebot': 'ClaudeBot',

        # Claude-User - Fetches URLs during user conversations (real-time citations)
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-User/1.0; +Claude-User@anthropic.com
        'claude-user': 'Claude-User',

        # Claude-SearchBot - Indexes websites for Claude's search feature
        'claude-searchbot': 'Claude-SearchBot',

        # Claude-Web - Alternative web access agent
        'claude-web': 'Claude-Web',

        # Anthropic-AI - Generic Anthropic identifier
        'anthropic-ai': 'Anthropic-AI',

        # Anthropic - Fallback for any Anthropic bot
        'anthropic': 'Anthropic',
        'claude': 'Claude',

        # ---------------------------------------------------------------------
        # OPENAI BOTS
        # Reference: https://darkvisitors.com/agents
        # ---------------------------------------------------------------------
        # GPTBot - Main crawler for training data collection
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot)
        'gptbot': 'OpenAI GPTBot',

        # ChatGPT-User - Fetches URLs during user conversations (real-time citations)
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot
        'chatgpt-user': 'ChatGPT-User',

        # OAI-SearchBot - Indexes websites for SearchGPT
        # Example: Mozilla/5.0 ... OAI-SearchBot/1.3; robots.txt; +https://openai.com/searchbot
        'oai-searchbot': 'OpenAI SearchBot',

        # ChatGPT-Agent - Agentic browser for multi-step tasks (Operator)
        # Note: May use standard browser UA, identified by other means
        'chatgpt-agent': 'ChatGPT Agent',
        'chatgpt': 'ChatGPT',
        'openai': 'OpenAI',

        # ---------------------------------------------------------------------
        # PERPLEXITY BOTS
        # Reference: https://darkvisitors.com/agents
        # ---------------------------------------------------------------------
        # PerplexityBot - Main crawler for indexing
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)
        'perplexitybot': 'PerplexityBot',

        # Perplexity-User - Fetches URLs during user conversations (real-time citations)
        # Example: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)
        'perplexity-user': 'Perplexity-User',

        # Perplexity - Fallback pattern
        'perplexity': 'Perplexity',

        # ---------------------------------------------------------------------
        # GOOGLE AI BOTS
        # Reference: https://darkvisitors.com/agents
        # ---------------------------------------------------------------------
        # Google-Extended - Used for Gemini/Vertex AI training
        'google-extended': 'Google-Extended',

        # Gemini-Deep-Research - Fetches resources for Gemini's Deep Research feature
        'gemini-deep-research': 'Gemini-Deep-Research',

        # Google-NotebookLM - Fetches source URLs for NotebookLM analysis
        'google-notebooklm': 'Google-NotebookLM',

        # Gemini - Google's AI assistant
        'gemini': 'Google Gemini',

        # Bard - Google's previous AI assistant name
        'bard': 'Google Bard',

        # ---------------------------------------------------------------------
        # OTHER AI/LLM BOTS
        # ---------------------------------------------------------------------
        # Cohere - Cohere AI crawler
        'cohere': 'Cohere',

        # Meta AI - User-initiated fetches for Meta AI assistant
        'meta-externalfetcher': 'Meta-ExternalFetcher',
        'meta-externalagent': 'Meta AI',

        # Apple - Applebot-Extended for Apple Intelligence features
        'applebot-extended': 'Applebot-Extended',

        # Bytespider - ByteDance/TikTok crawler (trains Doubao LLM)
        'bytespider': 'ByteSpider',

        # CCBot - Common Crawl bot (used for AI training datasets)
        'ccbot': 'CCBot',

        # YouBot - You.com AI search
        'youbot': 'YouBot',

        # ---------------------------------------------------------------------
        # SEARCH ENGINE BOTS
        # ---------------------------------------------------------------------
        'googlebot': 'GoogleBot',
        'bingbot': 'BingBot',
        'yandexbot': 'YandexBot',
        'duckduckbot': 'DuckDuckBot',
        'baiduspider': 'BaiduSpider',

        # ---------------------------------------------------------------------
        # SOCIAL MEDIA BOTS
        # ---------------------------------------------------------------------
        'slackbot': 'Slack',
        'facebookexternalhit': 'Facebook',
        'twitterbot': 'Twitter',
        'linkedinbot': 'LinkedIn',
        'discordbot': 'Discord',
        'telegrambot': 'Telegram',
        'whatsapp': 'WhatsApp',

        # ---------------------------------------------------------------------
        # DEVELOPER/TOOL BOTS
        # ---------------------------------------------------------------------
        'python-requests': 'Python Requests',
        'python-urllib': 'Python urllib',
        'aiohttp': 'Python aiohttp',
        'httpx': 'Python HTTPX',
        'node-fetch': 'Node.js Fetch',
        'axios': 'Axios',
        'curl': 'cURL',
        'wget': 'Wget',
        'postman': 'Postman',
        'insomnia': 'Insomnia',

        # ---------------------------------------------------------------------
        # INFRASTRUCTURE BOTS
        # ---------------------------------------------------------------------
        "let's encrypt": "Let's Encrypt",
        'letsencrypt': "Let's Encrypt",
        'uptimerobot': 'UptimeRobot',
        'pingdom': 'Pingdom',
        'statuscake': 'StatusCake',

        # ---------------------------------------------------------------------
        # GENERIC PATTERNS (checked last due to broad matching)
        # ---------------------------------------------------------------------
        'bot': 'Generic Bot',
        'crawler': 'Generic Crawler',
        'spider': 'Generic Spider',
        'scraper': 'Generic Scraper',
    }

    # ==========================================================================
    # LLM BOT CLASSIFICATION
    # ==========================================================================
    # Bots specifically used by AI/LLM companies for training or inference.
    # Used to calculate llm_bot_requests metric.
    # ==========================================================================

    LLM_BOTS = {
        # Anthropic/Claude
        'ClaudeBot',
        'Claude-User',
        'Claude-SearchBot',
        'Claude-Web',
        'Anthropic-AI',
        'Anthropic',
        'Claude',

        # OpenAI
        'OpenAI GPTBot',
        'ChatGPT-User',
        'OpenAI SearchBot',
        'ChatGPT Agent',
        'ChatGPT',
        'OpenAI',

        # Perplexity
        'PerplexityBot',
        'Perplexity-User',
        'Perplexity',

        # Google AI
        'Google-Extended',
        'Gemini-Deep-Research',
        'Google-NotebookLM',
        'Google Gemini',
        'Google Bard',

        # Other AI
        'Cohere',
        'Meta-ExternalFetcher',
        'Meta AI',
        'Applebot-Extended',
        'ByteSpider',
        'CCBot',
        'YouBot',
    }

    # ==========================================================================
    # BOT CATEGORIES BY PURPOSE
    # ==========================================================================
    # Categorize bots by their primary purpose to help understand what
    # traffic matters most for GEO (Generative Engine Optimization).
    #
    # Categories:
    # - training: Crawls content for model training (appears in future knowledge)
    # - citation: Real-time fetches during user conversations (MOST VALUABLE for GEO)
    # - search_index: Builds AI search engine indexes (powers SearchGPT, etc.)
    # - agent: Agentic browser usage for multi-step tasks
    # ==========================================================================

    BOT_CATEGORIES = {
        # Training bots - crawl content for model training
        'ClaudeBot': 'training',
        'OpenAI GPTBot': 'training',
        'Google-Extended': 'training',
        'Applebot-Extended': 'training',
        'ByteSpider': 'training',
        'CCBot': 'training',
        'Cohere': 'training',
        'YouBot': 'training',
        'Google Gemini': 'training',
        'Google Bard': 'training',
        'Anthropic-AI': 'training',
        'Anthropic': 'training',
        'Claude': 'training',
        'Claude-Web': 'training',
        'Meta AI': 'training',
        'Perplexity': 'training',
        'ChatGPT': 'training',
        'OpenAI': 'training',

        # Citation bots - real-time fetches during user conversations
        # These are the MOST VALUABLE for GEO - they directly lead to citations!
        'Claude-User': 'citation',
        'ChatGPT-User': 'citation',
        'Perplexity-User': 'citation',
        'Meta-ExternalFetcher': 'citation',
        'Gemini-Deep-Research': 'citation',
        'Google-NotebookLM': 'citation',

        # Search index bots - build AI search indexes
        # These crawl content to build the search indexes that power organic citations
        'PerplexityBot': 'search_index',  # PRIMARY driver of Perplexity citations
        'Claude-SearchBot': 'search_index',
        'OpenAI SearchBot': 'search_index',

        # Agent bots - agentic browser usage for multi-step tasks
        'ChatGPT Agent': 'agent',
    }

    CATEGORY_DESCRIPTIONS = {
        'citation': '🎯 User/Citation Bots (real-time requests)',
        'search_index': '🔍 Search Index Bots (building AI search indexes)',
        'training': '📚 Training Bots (content collection for model training)',
        'agent': '🤖 Agent Bots (agentic browser tasks)',
    }

    # Order for displaying categories (most important first)
    CATEGORY_ORDER = ['citation', 'search_index', 'training', 'agent']

    # ==========================================================================
    # CLAUDE-SPECIFIC PATTERNS
    # ==========================================================================
    # For detailed Claude crawler analysis. Used by claude_crawler_analysis.py.
    # ==========================================================================

    CLAUDE_PATTERNS = [
        'claudebot',
        'claude-user',
        'claude-searchbot',
        'claude-web',
        'anthropic-ai',
        'anthropic',
    ]

    def __init__(self, logs_bucket: str = None, logs_prefix: str = 'geo-logs/', excluded_ips: List[str] = None):
        # Ensure environment variables are loaded from project root if not already
        load_dotenv()
        
        # Use provided bucket or fallback to environment variable, then hardcoded default
        self.logs_bucket = logs_bucket or os.getenv("AWS_LOGS_BUCKET") or 'rozzum-cloudfront-logs'
        self.logs_prefix = logs_prefix or 'geo-logs/'
        
        # Process excluded IPs into hashes
        self.excluded_ip_hashes = set()
        if excluded_ips:
            for ip in excluded_ips:
                if ip.strip():
                    self.excluded_ip_hashes.add(self.hash_ip(ip.strip()))

        # Initialize boto3 session using GEO-specific environment variables
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID_GEO") or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY_GEO") or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-west-2")
        
        # Diagnostic logging (masked for security)
        if aws_access_key:
            masked_key = f"{aws_access_key[:5]}...{aws_access_key[-4:]}"
            msg = f"ℹ️ GEO Analytics: Using AWS Access Key {masked_key}"
            # print(msg)
            log_worker("system", msg, worker="geo_analytics")
        else:
            msg = "ℹ️ GEO Analytics: No AWS_ACCESS_KEY_ID_GEO or AWS_ACCESS_KEY_ID found in environment"
            # print(msg)
            log_worker("system", msg, worker="geo_analytics", level="WARNING")

        try:
            if aws_access_key and aws_secret_key:
                self.s3 = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                # Fallback to default credential resolution
                self.s3 = boto3.client('s3', region_name=aws_region)
                
        except Exception as e:
            msg = f"⚠️ AWS S3 Initialization Warning: {str(e)}"
            print(msg)
            log_worker("system", msg, worker="geo_analytics", level="ERROR")
            self.s3 = boto3.client('s3')

    def identify_bot(self, user_agent: str) -> str:
        """Identify bot from User-Agent string."""
        if not user_agent or user_agent == '-':
            return 'Unknown'

        user_agent_lower = user_agent.lower()

        # Check specific bot patterns
        for pattern, name in self.BOT_PATTERNS.items():
            if pattern in user_agent_lower:
                return name

        # Check if it looks like a browser
        browser_indicators = ['mozilla', 'chrome', 'safari', 'firefox', 'edge']
        if any(browser in user_agent_lower for browser in browser_indicators):
            # But exclude if it also has bot indicators
            if 'bot' not in user_agent_lower and 'crawler' not in user_agent_lower:
                return 'Human Browser'

        return 'Other Bot'

    def hash_ip(self, ip: str) -> str:
        """Hash IP address for privacy (SHA256)."""
        if not ip or ip == '-':
            return None
        return hashlib.sha256(ip.encode()).hexdigest()

    def categorize_uri(self, uri: str) -> str:
        """Categorize URI by content type."""
        uri = uri.lower()

        if uri.startswith('/qna/') and uri.endswith('.html'):
            return 'Q&A Page'
        elif uri.startswith('/pages/') and uri.endswith('.html'):
            return 'GEO Page'
        elif uri == '/' or uri == '/index.html':
            return 'Homepage'
        elif uri == '/llms.txt':
            return 'LLMs.txt'
        elif uri == '/sitemap.xml':
            return 'Sitemap'
        elif uri == '/robots.txt':
            return 'Robots.txt'
        elif uri.startswith('/api/'):
            if 'qna.json' in uri:
                return 'Q&A API'
            elif 'pages.json' in uri:
                return 'Pages API'
            elif 'topics.json' in uri:
                return 'Topics API'
            elif 'search.json' in uri:
                return 'Search API'
            return 'API'
        
        # Additional categories for rozz.site
        common_pages = ['/demo', '/about', '/pricing', '/contact', '/features']
        if any(uri.startswith(p) for p in common_pages):
            return 'Main Page'
            
        return 'Other'

    def extract_slug(self, uri: str, content_type: str) -> Optional[str]:
        """Extract slug from URI based on content type."""
        if content_type == 'Q&A Page':
            # /qna/slug.html -> slug
            match = re.search(r'/qna/([^/]+)\.html', uri)
            return match.group(1) if match else None
        elif content_type == 'GEO Page':
            # /pages/slug.html -> slug
            match = re.search(r'/pages/([^/]+)\.html', uri)
            return match.group(1) if match else None
        elif content_type in ['Q&A API', 'Pages API', 'Topics API', 'Search API']:
            # Extract endpoint name
            if 'qna.json' in uri:
                return 'qna.json'
            elif 'pages.json' in uri:
                return 'pages.json'
            elif 'topics.json' in uri:
                return 'topics.json'
            elif 'search.json' in uri:
                return 'search.json'
        return None

    def parse_log_file(self, s3_key: str) -> List[Dict]:
        """Parse a single CloudFront log file."""
        try:
            # Download log file
            response = self.s3.get_object(Bucket=self.logs_bucket, Key=s3_key)

            # CloudFront logs are gzipped
            if s3_key.endswith('.gz'):
                content = gzip.decompress(response['Body'].read()).decode('utf-8')
            else:
                content = response['Body'].read().decode('utf-8')

            # Parse TSV format (skip comment lines starting with #)
            lines = [line for line in content.split('\n') if line and not line.startswith('#')]

            if not lines:
                return []

            # CloudFront log fields (version 1.0)
            fieldnames = [
                'date', 'time', 'x-edge-location', 'sc-bytes', 'c-ip', 'cs-method',
                'cs-host', 'cs-uri-stem', 'sc-status', 'cs-referer', 'cs-user-agent',
                'cs-uri-query', 'cs-cookie', 'x-edge-result-type', 'x-edge-request-id',
                'x-host-header', 'cs-protocol', 'cs-bytes', 'time-taken',
                'x-forwarded-for', 'ssl-protocol', 'ssl-cipher', 'x-edge-response-result-type'
            ]

            records = []
            reader = csv.DictReader(lines, fieldnames=fieldnames, delimiter='\t')

            for row in reader:
                # Parse relevant fields
                # Add +0000 offset to ensure parsed as UTC
                timestamp = f"{row['date']} {row['time']} +0000"
                uri = unquote(row['cs-uri-stem'])
                user_agent = unquote(row['cs-user-agent']) if row['cs-user-agent'] != '-' else ''
                status = row['sc-status']
                ip = row['c-ip']
                referer = unquote(row['cs-referer']) if row['cs-referer'] != '-' else None

                # Identify bot
                bot_name = self.identify_bot(user_agent)

                # Categorize content type
                content_type = self.categorize_uri(uri)

                # Extract slug if applicable
                slug = self.extract_slug(uri, content_type)

                # Hash IP for privacy
                ip_hash = self.hash_ip(ip)

                # Extract host header for multi-domain filtering
                host_header = row.get('x-host-header', '')

                records.append({
                    'timestamp': timestamp,
                    'uri': uri,
                    'status': status,
                    'ip': ip,
                    'ip_hash': ip_hash,
                    'user_agent': user_agent,
                    'bot_name': bot_name,
                    'referer': referer,
                    'content_type': content_type,
                    'slug': slug,
                    'host_header': host_header
                })

            return records

        except Exception as e:
            print(f"Error parsing {s3_key}: {e}")
            return []

    def get_log_files(self, days: int = None, start_date: datetime = None, end_date: datetime = None) -> List[str]:
        """Get list of log files for a specific date range or past N days.

        Filters by the date embedded in the filename (DIST_ID.YYYY-MM-DD-HH.hash.gz),
        not by S3 LastModified timestamp, to avoid double-counting files whose
        LastModified bleeds into adjacent days.
        """
        if days is not None:
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()

        # Normalize to date objects for filename comparison
        if start_date:
            if isinstance(start_date, date) and not isinstance(start_date, datetime):
                start_d = start_date
            else:
                start_d = start_date.date() if hasattr(start_date, 'date') else start_date
        else:
            start_d = None

        if end_date:
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                end_d = end_date
            else:
                end_d = end_date.date() if hasattr(end_date, 'date') else end_date
        else:
            end_d = None

        paginator = self.s3.get_paginator('list_objects_v2')
        log_files = []

        # CloudFront log filenames: DIST_ID.YYYY-MM-DD-HH.UNIQUE_ID.gz
        # Use per-date S3 prefix to avoid listing the entire bucket
        if start_d and end_d:
            # Generate prefixes for each date in range
            current = start_d
            prefixes = []
            while current <= end_d:
                prefixes.append(f"{self.logs_prefix}E10VK3E8XVQWI5.{current.isoformat()}")
                current += timedelta(days=1)
        else:
            prefixes = [self.logs_prefix]

        for prefix in prefixes:
            for page in paginator.paginate(Bucket=self.logs_bucket, Prefix=prefix):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    log_files.append(obj['Key'])

        return sorted(log_files)

    def analyze_logs(self, domain: str = None, days: int = None, start_date: datetime = None, end_date: datetime = None) -> Dict:
        """Analyze logs for a specific date range or past N days."""
        log_files = self.get_log_files(days=days, start_date=start_date, end_date=end_date)

        domain_for_log = domain or "system"
        if log_files:
            msg = f"Found {len(log_files)} log files to process..."
            print(msg)
            log_worker(domain_for_log, msg, worker="geo_analytics")
        else:
            # Don't print "Found 0" if we weren't expecting any
            if days or start_date:
                msg = "No log files found for the specified period."
                print(msg)
                log_worker(domain_for_log, msg, worker="geo_analytics", level="WARNING")
            return self.calculate_stats([])

        # Parse all log files
        all_records = []
        for i, log_file in enumerate(log_files, 1):
            if i % 10 == 0 or i == len(log_files):
                msg = f"  Processing file {i}/{len(log_files)}..."
                print(msg)
                log_worker(domain_for_log, msg, worker="geo_analytics")

            records = self.parse_log_file(log_file)
            all_records.extend(records)

        msg = f"Parsed {len(all_records)} total requests"
        print(msg)
        log_worker(domain_for_log, msg, worker="geo_analytics")

        # Filter by domain using x-host-header field from CloudFront logs
        if domain:
            # Filter records where host_header matches the domain or rozz.{domain}
            # This handles cases where the host header might be either the base domain 
            # or the rozz-prefixed GEO subdomain.
            rozz_domain = f"rozz.{domain}"
            domain_records = [
                r for r in all_records 
                if r.get('host_header') == domain or r.get('host_header') == rozz_domain
            ]
            msg = f"Filtered to {len(domain_records)} requests for domain: {domain} (matches: {domain}, {rozz_domain})"
            print(msg)
            log_worker(domain_for_log, msg, worker="geo_analytics")
        else:
            domain_records = all_records

        # Calculate statistics
        stats = self.calculate_stats(domain_records)

        return stats

    def _detect_scanner_ips(self, records: List[Dict]) -> set:
        """Identify IPs whose traffic looks like a vulnerability scan.

        Flagged when a single IP produces more than SCANNER_REQUEST_THRESHOLD
        requests AND its dominant bot_name is in SCANNER_SUSPICIOUS_BOTS.
        Known LLM/search crawlers are never flagged.
        """
        ip_count = Counter()
        ip_bots = defaultdict(Counter)
        for r in records:
            iph = r.get('ip_hash')
            if not iph:
                continue
            ip_count[iph] += 1
            ip_bots[iph][r.get('bot_name') or 'Unknown'] += 1

        scanners = set()
        for iph, count in ip_count.items():
            if count <= self.SCANNER_REQUEST_THRESHOLD:
                continue
            top_bot, _ = ip_bots[iph].most_common(1)[0]
            if top_bot in self.SCANNER_SUSPICIOUS_BOTS:
                scanners.add(iph)
        return scanners

    def calculate_stats(self, records: List[Dict]) -> Dict:
        """Calculate analytics from parsed records."""
        # Filter out records from excluded IP hashes
        if self.excluded_ip_hashes:
            orig_count = len(records)
            records = [r for r in records if r['ip_hash'] not in self.excluded_ip_hashes]
            if len(records) < orig_count:
                print(f"Filtered out {orig_count - len(records)} requests from excluded IPs")

        # Auto-detect scanner/scraper IPs: single IP producing an abnormally
        # high volume of requests under a suspicious user-agent (cURL,
        # generic bot, etc.) — typically vulnerability scans. Keeps raw S3
        # logs intact; only analytics/dashboards drop these.
        scanner_ips = self._detect_scanner_ips(records)
        if scanner_ips:
            orig_count = len(records)
            records = [r for r in records if r['ip_hash'] not in scanner_ips]
            dropped = orig_count - len(records)
            print(f"Auto-filtered {dropped} requests from {len(scanner_ips)} scanner IP(s) "
                  f"(>{self.SCANNER_REQUEST_THRESHOLD} req, suspicious UA)")

        stats = {
            'total_requests': len(records),
            'unique_ips': len(set(r['ip_hash'] for r in records if r['ip_hash'])),
            'by_content_type': Counter(r['content_type'] for r in records),
            'by_bot': Counter(r['bot_name'] for r in records),
            'by_status': Counter(r['status'] for r in records),
            'top_qnas': Counter(r['slug'] for r in records if r['content_type'] == 'Q&A Page' and r['slug']).most_common(20),
            'top_pages': Counter(r['slug'] for r in records if r['content_type'] == 'GEO Page' and r['slug']).most_common(20),
            'top_apis': Counter(r['slug'] for r in records if 'API' in r['content_type'] and r['slug']).most_common(10),
            'bot_activity': defaultdict(lambda: defaultdict(int)),
            'hourly_traffic': defaultdict(int),
            'daily_traffic': defaultdict(int),
            'llm_bot_requests': 0,
            'human_requests': 0,
            'bot_requests': 0,
            'by_bot_category': defaultdict(lambda: {'count': 0, 'bots': Counter()}),
            'records': records  # Keep for database insertion
        }

        # Bot activity by content type and time distribution
        for record in records:
            bot = record['bot_name']
            content_type = record['content_type']
            stats['bot_activity'][bot][content_type] += 1

            # Hourly distribution
            hour = record['timestamp'][:13]  # YYYY-MM-DD HH
            stats['hourly_traffic'][hour] += 1

            # Daily distribution
            day = record['timestamp'][:10]  # YYYY-MM-DD
            stats['daily_traffic'][day] += 1

            # Count bot types
            if bot in self.LLM_BOTS:
                stats['llm_bot_requests'] += 1

                # Track by category
                category = self.BOT_CATEGORIES.get(bot, 'unknown')
                stats['by_bot_category'][category]['count'] += 1
                stats['by_bot_category'][category]['bots'][bot] += 1

            if bot == 'Human Browser':
                stats['human_requests'] += 1
            else:
                stats['bot_requests'] += 1

        return stats

    def generate_report(self, domain: str = None, days: int = 7) -> str:
        """Generate human-readable analytics report."""
        stats = self.analyze_logs(domain, days)

        report = f"""
# GEO Analytics Report{f': {domain}' if domain else ''}
## Period: Last {days} days

### Overview
- **Total Requests**: {stats['total_requests']:,}
- **Unique IPs**: {stats['unique_ips']:,}
- **Success Rate**: {(stats['by_status'].get('200', 0) / max(stats['total_requests'], 1) * 100):.1f}%
- **Human Requests**: {stats['human_requests']:,} ({stats['human_requests'] / max(stats['total_requests'], 1) * 100:.1f}%)
- **Bot Requests**: {stats['bot_requests']:,} ({stats['bot_requests'] / max(stats['total_requests'], 1) * 100:.1f}%)
- **LLM Bot Requests**: {stats['llm_bot_requests']:,} ({stats['llm_bot_requests'] / max(stats['total_requests'], 1) * 100:.1f}%)

### Content Type Distribution
"""
        for content_type, count in stats['by_content_type'].most_common():
            pct = count / max(stats['total_requests'], 1) * 100
            report += f"- **{content_type}**: {count:,} ({pct:.1f}%)\n"

        report += "\n### Bot/Crawler Activity\n"
        for bot, count in stats['by_bot'].most_common(15):
            pct = count / max(stats['total_requests'], 1) * 100
            llm_indicator = " 🤖" if bot in self.LLM_BOTS else ""
            report += f"- **{bot}**{llm_indicator}: {count:,} ({pct:.1f}%)\n"

        # LLM Bot Activity by Purpose Category
        report += "\n### LLM Bot Activity by Purpose\n"
        report += "_Understanding bot purposes helps prioritize GEO efforts._\n\n"

        for category in self.CATEGORY_ORDER:
            cat_data = stats['by_bot_category'].get(category, {'count': 0, 'bots': Counter()})
            cat_desc = self.CATEGORY_DESCRIPTIONS.get(category, category)
            report += f"\n**{cat_desc}**\n"

            if cat_data['count'] > 0:
                for bot, count in cat_data['bots'].most_common():
                    report += f"- {bot}: {count:,} requests\n"
            else:
                report += "- No requests\n"

        report += "\n### Top Q&A Pages\n"
        if stats['top_qnas']:
            for slug, count in stats['top_qnas'][:10]:
                report += f"- `{slug}`: {count:,} views\n"
        else:
            report += "- No Q&A page views\n"

        report += "\n### Top GEO Pages\n"
        if stats['top_pages']:
            for slug, count in stats['top_pages'][:10]:
                report += f"- `{slug}`: {count:,} views\n"
        else:
            report += "- No GEO page views\n"

        report += "\n### API Usage\n"
        if stats['top_apis']:
            for endpoint, count in stats['top_apis']:
                report += f"- `/api/{endpoint}`: {count:,} requests\n"
        else:
            report += "- No API requests\n"

        report += "\n### LLM Bot Behavior by Content Type\n"
        for bot in self.LLM_BOTS:
            if bot in stats['bot_activity']:
                content_counts = stats['bot_activity'][bot]
                total = sum(content_counts.values())
                report += f"\n**{bot}** ({total:,} requests):\n"
                for content_type, count in sorted(content_counts.items(), key=lambda x: -x[1])[:5]:
                    pct = count / total * 100
                    report += f"  - {content_type}: {count:,} ({pct:.1f}%)\n"

        report += "\n### Daily Traffic\n"
        for day in sorted(stats['daily_traffic'].keys(), reverse=True):
            count = stats['daily_traffic'][day]
            report += f"- {day}: {count:,} requests\n"

        return report


if __name__ == "__main__":
    # Example usage
    analytics = GeoAnalytics(
        logs_bucket='rozzum-cloudfront-logs',
        logs_prefix='geo-logs/'
    )

    report = analytics.generate_report(domain='rozz.site', days=7)
    print(report)
