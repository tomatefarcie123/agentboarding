#!/usr/bin/env python3
"""
Claude Crawler Behavior Analysis

Analyzes ClaudeBot crawl patterns to understand:
- Discovery sequence (robots.txt, llms.txt, sitemap, APIs)
- What files are accessed vs ignored
- Crawl timing and sessions
- Content type preferences

Usage:
    cd "/Users/adrienschmidt/Documents/Code Projects/chatbot"

    # Analyze Claude crawler behavior for a domain
    PYTHONPATH=. venv-embeddings/bin/python analytics/claude_crawler_analysis.py --domain genymotion.com
    PYTHONPATH=. venv-embeddings/bin/python analytics/claude_crawler_analysis.py --domain genymotion.com --days 60
    PYTHONPATH=. venv-embeddings/bin/python analytics/claude_crawler_analysis.py --domain genymotion.com --output report.md

    # List all bots seen across all domains
    PYTHONPATH=. venv-embeddings/bin/python analytics/claude_crawler_analysis.py --list-bots
    PYTHONPATH=. venv-embeddings/bin/python analytics/claude_crawler_analysis.py --list-bots --days 60
"""

import argparse
from collections import defaultdict, Counter
from datetime import datetime
from typing import List, Dict, Any

from analytics.geo_analytics import GeoAnalytics


# Use centralized patterns from GeoAnalytics
CLAUDE_PATTERNS = GeoAnalytics.CLAUDE_PATTERNS

# Discovery files to track
DISCOVERY_FILES = [
    '/robots.txt',
    '/llms.txt',
    '/llms-full.txt',
    '/sitemap.xml',
    '/api/qna.json',
    '/api/pages.json',
    '/api/topics.json',
    '/api/search.json',
]


def is_claude_bot(user_agent: str) -> bool:
    """Check if user agent is a Claude/Anthropic bot."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(pattern in ua_lower for pattern in CLAUDE_PATTERNS)


def get_claude_visits(analytics: GeoAnalytics, domain: str, days: int) -> List[Dict]:
    """Extract all Claude bot visits for a domain."""
    log_files = analytics.get_log_files(days=days)
    print(f'Processing {len(log_files)} log files for {days} days...')

    # The host header includes rozz. prefix
    host_header = f'rozz.{domain}'

    claude_visits = []
    for i, log_file in enumerate(log_files, 1):
        if i % 50 == 0:
            print(f'  {i}/{len(log_files)}...')

        records = analytics.parse_log_file(log_file)
        for r in records:
            if r.get('host_header') != host_header:
                continue

            if is_claude_bot(r.get('user_agent', '')):
                claude_visits.append(r)

    # Sort by timestamp
    claude_visits.sort(key=lambda x: x['timestamp'])
    return claude_visits


def analyze_discovery_sequence(visits: List[Dict]) -> Dict[str, Any]:
    """Analyze the order in which Claude discovers content."""
    first_of_type = {}

    for v in visits:
        ct = v['content_type']
        if ct not in first_of_type:
            first_of_type[ct] = v

    # Also track first access to specific discovery files
    first_discovery = {}
    for v in visits:
        uri = v['uri']
        if uri in DISCOVERY_FILES and uri not in first_discovery:
            first_discovery[uri] = v

    return {
        'first_by_content_type': first_of_type,
        'first_discovery_files': first_discovery
    }


def analyze_sessions(visits: List[Dict], gap_minutes: int = 60) -> List[List[Dict]]:
    """Group visits into sessions (gaps > gap_minutes = new session)."""
    if not visits:
        return []

    sessions = []
    current_session = [visits[0]]

    for i in range(1, len(visits)):
        prev_time = datetime.strptime(visits[i-1]['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
        curr_time = datetime.strptime(visits[i]['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
        gap = (curr_time - prev_time).total_seconds() / 60

        if gap > gap_minutes:
            sessions.append(current_session)
            current_session = []

        current_session.append(visits[i])

    if current_session:
        sessions.append(current_session)

    return sessions


def analyze_file_access(visits: List[Dict]) -> Dict[str, int]:
    """Count access to discovery files."""
    access_counts = {f: 0 for f in DISCOVERY_FILES}

    for v in visits:
        uri = v['uri']
        if uri in access_counts:
            access_counts[uri] += 1

    return access_counts


def analyze_content_preferences(visits: List[Dict]) -> Dict[str, Any]:
    """Analyze what content types Claude prefers."""
    by_type = Counter(v['content_type'] for v in visits)

    # Status codes by content type
    status_by_type = defaultdict(Counter)
    for v in visits:
        status_by_type[v['content_type']][v['status']] += 1

    return {
        'by_content_type': by_type,
        'status_by_type': dict(status_by_type)
    }


def analyze_crawl_timing(visits: List[Dict]) -> Dict[str, Any]:
    """Analyze crawl timing patterns."""
    if not visits:
        return {}

    # Find sitemap access and first page crawl
    sitemap_time = None
    first_page_time = None

    for v in visits:
        if v['uri'] == '/sitemap.xml' and not sitemap_time:
            sitemap_time = v['timestamp']
        if v['content_type'] in ['GEO Page', 'Q&A Page'] and not first_page_time:
            first_page_time = v['timestamp']

    gap_hours = None
    if sitemap_time and first_page_time:
        t1 = datetime.strptime(sitemap_time[:19], '%Y-%m-%d %H:%M:%S')
        t2 = datetime.strptime(first_page_time[:19], '%Y-%m-%d %H:%M:%S')
        gap_hours = (t2 - t1).total_seconds() / 3600

    # Hourly distribution
    hourly = Counter()
    daily = Counter()
    for v in visits:
        hourly[v['timestamp'][11:13]] += 1
        daily[v['timestamp'][:10]] += 1

    return {
        'sitemap_access': sitemap_time,
        'first_page_crawl': first_page_time,
        'sitemap_to_crawl_gap_hours': gap_hours,
        'hourly_distribution': dict(hourly),
        'daily_distribution': dict(daily)
    }


def generate_report(domain: str, visits: List[Dict], days: int) -> str:
    """Generate a markdown report of the analysis."""

    discovery = analyze_discovery_sequence(visits)
    sessions = analyze_sessions(visits)
    file_access = analyze_file_access(visits)
    content_prefs = analyze_content_preferences(visits)
    timing = analyze_crawl_timing(visits)

    # Unique user agents
    unique_agents = set(v.get('user_agent', '')[:100] for v in visits)

    # Build report
    report = []
    report.append(f"# Claude Crawler Behavior Analysis: {domain}")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Analysis Period:** Last {days} days")
    report.append(f"**Total Claude Visits:** {len(visits)}")
    report.append(f"**Sessions Identified:** {len(sessions)}")

    # User Agents
    report.append("\n---\n")
    report.append("## User-Agent Strings")
    for ua in sorted(unique_agents):
        if ua:
            report.append(f"```\n{ua}\n```")

    # Discovery Sequence
    report.append("\n---\n")
    report.append("## 1. Discovery Sequence")
    report.append("\n### First Access by Content Type")
    report.append("| Timestamp | Status | Content Type | URI |")
    report.append("|-----------|--------|--------------|-----|")

    for ct, v in sorted(discovery['first_by_content_type'].items(),
                        key=lambda x: x[1]['timestamp']):
        status = '✅' if v['status'] == '200' else '❌'
        uri = v['uri'][:50] + '...' if len(v['uri']) > 50 else v['uri']
        report.append(f"| {v['timestamp'][:19]} | {status} | {ct} | `{uri}` |")

    report.append("\n### Discovery Files Access Order")
    for uri, v in sorted(discovery['first_discovery_files'].items(),
                         key=lambda x: x[1]['timestamp']):
        status = '✅' if v['status'] == '200' else '❌'
        report.append(f"- {v['timestamp'][:19]} {status} `{uri}`")

    # File Access Counts
    report.append("\n---\n")
    report.append("## 2. Discovery File Access")
    report.append("\n| File | Access Count | Status |")
    report.append("|------|-------------|--------|")

    for file, count in file_access.items():
        status = '✅ Used' if count > 0 else '❌ Never accessed'
        report.append(f"| `{file}` | {count} | {status} |")

    # Sessions
    report.append("\n---\n")
    report.append("## 3. Crawl Sessions")
    report.append(f"\n**Total Sessions:** {len(sessions)}")

    for i, session in enumerate(sessions, 1):
        start = session[0]['timestamp'][:19]
        end = session[-1]['timestamp'][:19]

        t1 = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
        t2 = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
        duration_sec = (t2 - t1).total_seconds()

        types = Counter(v['content_type'] for v in session)

        report.append(f"\n### Session {i}: {start}")
        report.append(f"- **Duration:** {duration_sec:.0f} seconds ({duration_sec/60:.1f} min)")
        report.append(f"- **Total Requests:** {len(session)}")
        report.append(f"- **Content Breakdown:**")
        for ct, count in types.most_common():
            report.append(f"  - {ct}: {count}")

        # First 5 requests
        report.append(f"- **First Requests:**")
        for v in session[:5]:
            status = '✅' if v['status'] == '200' else '❌'
            uri = v['uri'][:45] + '...' if len(v['uri']) > 45 else v['uri']
            report.append(f"  - {v['timestamp'][11:19]} {status} {v['content_type']}: `{uri}`")

    # Content Preferences
    report.append("\n---\n")
    report.append("## 4. Content Type Preferences")
    report.append("\n| Content Type | Requests | Success Rate |")
    report.append("|--------------|----------|--------------|")

    for ct, count in content_prefs['by_content_type'].most_common():
        statuses = content_prefs['status_by_type'].get(ct, {})
        success = statuses.get('200', 0)
        rate = success / count * 100 if count else 0
        report.append(f"| {ct} | {count} | {rate:.1f}% |")

    # Timing Analysis
    report.append("\n---\n")
    report.append("## 5. Crawl Timing")

    if timing.get('sitemap_access') and timing.get('first_page_crawl'):
        report.append(f"\n- **Sitemap accessed:** {timing['sitemap_access'][:19]}")
        report.append(f"- **First page crawled:** {timing['first_page_crawl'][:19]}")
        if timing.get('sitemap_to_crawl_gap_hours') is not None:
            report.append(f"- **Gap:** {timing['sitemap_to_crawl_gap_hours']:.1f} hours")

    report.append("\n### Daily Distribution")
    report.append("| Date | Requests |")
    report.append("|------|----------|")
    for date in sorted(timing.get('daily_distribution', {}).keys(), reverse=True):
        count = timing['daily_distribution'][date]
        report.append(f"| {date} | {count} |")

    # Key Insights
    report.append("\n---\n")
    report.append("## 6. Key Insights")

    # Bot purpose explanation
    report.append("\n### Understanding Claude Bot Types")
    report.append("""
| Bot | Purpose | GEO Value |
|-----|---------|-----------|
| **ClaudeBot** | Training data collection | Content may appear in future model knowledge |
| **Claude-User** | Real-time fetches during conversations | **HIGHEST** - Direct path to citations |
| **Claude-SearchBot** | Building Claude's search index | High - Powers Claude's web search |
""")

    # llms-full.txt usage
    llms_full_count = file_access.get('/llms-full.txt', 0)
    llms_count = file_access.get('/llms.txt', 0)

    report.append("\n### Discovery File Usage")
    if llms_full_count > 0:
        report.append(f"- ✅ **llms-full.txt accessed {llms_full_count} times** - Claude is using full content file!")
    else:
        report.append(f"- ❌ **llms-full.txt never accessed** - Claude prefers HTML page crawls")

    if llms_count > 0:
        report.append(f"- ✅ llms.txt accessed {llms_count} times")

    # API vs HTML
    api_count = sum(1 for v in visits if 'API' in v['content_type'])
    html_count = sum(1 for v in visits if v['content_type'] in ['GEO Page', 'Q&A Page'])

    report.append("\n### Content Consumption")
    report.append(f"- API requests: {api_count}")
    report.append(f"- HTML page requests: {html_count}")
    if html_count > api_count * 10:
        report.append(f"- **Insight:** Claude strongly prefers HTML pages over APIs ({html_count}x vs {api_count}x)")

    # Crawl rate
    if sessions:
        biggest_session = max(sessions, key=len)
        if len(biggest_session) > 100:
            start = datetime.strptime(biggest_session[0]['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(biggest_session[-1]['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
            duration = (end - start).total_seconds()
            if duration > 0:
                rate = len(biggest_session) / duration
                report.append(f"\n### Crawl Rate")
                report.append(f"- Peak session: {len(biggest_session)} requests in {duration:.0f} seconds")
                report.append(f"- Average rate: {rate:.1f} requests/second")

    report.append("\n---\n")
    report.append(f"*Generated by claude_crawler_analysis.py*")

    return '\n'.join(report)


def list_all_bots(analytics: GeoAnalytics, days: int) -> None:
    """List all bots seen in CloudFront logs with their user agents."""
    log_files = analytics.get_log_files(days=days)
    print(f'Processing {len(log_files)} log files for {days} days...')

    # Collect all user agents and their bot classifications
    bot_user_agents = defaultdict(Counter)  # bot_name -> {user_agent: count}
    host_by_bot = defaultdict(Counter)  # bot_name -> {host: count}
    total_by_bot = Counter()

    for i, log_file in enumerate(log_files, 1):
        if i % 50 == 0:
            print(f'  {i}/{len(log_files)}...')

        records = analytics.parse_log_file(log_file)
        for r in records:
            bot_name = r.get('bot_name', 'Unknown')
            user_agent = r.get('user_agent', '')[:150]  # Truncate long UAs
            host = r.get('host_header', 'unknown')

            total_by_bot[bot_name] += 1
            bot_user_agents[bot_name][user_agent] += 1
            host_by_bot[bot_name][host] += 1

    # Print report
    print("\n" + "=" * 80)
    print("  ALL BOTS DETECTED IN CLOUDFRONT LOGS")
    print("=" * 80)
    print(f"\nAnalysis period: Last {days} days")
    print(f"Total bot types detected: {len(total_by_bot)}")

    # Separate LLM bots from others
    llm_bots = {b: c for b, c in total_by_bot.items() if b in GeoAnalytics.LLM_BOTS}
    other_bots = {b: c for b, c in total_by_bot.items() if b not in GeoAnalytics.LLM_BOTS}

    print("\n" + "-" * 80)
    print("  LLM / AI BOTS")
    print("-" * 80)

    if llm_bots:
        for bot_name, count in sorted(llm_bots.items(), key=lambda x: -x[1]):
            print(f"\n🤖 {bot_name}: {count:,} requests")

            # Show user agents
            print("   User-Agent(s):")
            for ua, ua_count in bot_user_agents[bot_name].most_common(3):
                print(f"      [{ua_count}x] {ua}")

            # Show which domains
            print("   Domains accessed:")
            for host, host_count in host_by_bot[bot_name].most_common(5):
                print(f"      {host}: {host_count}")
    else:
        print("\n   No LLM bots detected in this period.")

    print("\n" + "-" * 80)
    print("  SEARCH ENGINE BOTS")
    print("-" * 80)

    search_bots = ['GoogleBot', 'BingBot', 'YandexBot', 'DuckDuckBot', 'BaiduSpider']
    for bot_name in search_bots:
        if bot_name in other_bots:
            count = other_bots[bot_name]
            print(f"\n🔍 {bot_name}: {count:,} requests")
            for host, host_count in host_by_bot[bot_name].most_common(3):
                print(f"      {host}: {host_count}")

    print("\n" + "-" * 80)
    print("  OTHER BOTS")
    print("-" * 80)

    remaining = {b: c for b, c in other_bots.items() if b not in search_bots}
    for bot_name, count in sorted(remaining.items(), key=lambda x: -x[1])[:15]:
        print(f"\n   {bot_name}: {count:,} requests")
        # Show first user agent
        if bot_user_agents[bot_name]:
            ua = list(bot_user_agents[bot_name].keys())[0]
            print(f"      UA: {ua[:80]}...")

    print("\n" + "=" * 80)
    print("  BOT PATTERN REFERENCE (from GeoAnalytics.BOT_PATTERNS)")
    print("=" * 80)

    print("\n### LLM Bots We're Looking For:")
    for bot in sorted(GeoAnalytics.LLM_BOTS):
        seen = "✅ SEEN" if bot in total_by_bot else "❌ Not seen"
        count = total_by_bot.get(bot, 0)
        print(f"   {bot:25} {seen} ({count:,} requests)")

    print("\n### Claude-Specific Patterns:")
    for pattern in GeoAnalytics.CLAUDE_PATTERNS:
        # Check if any bot matching this pattern was seen
        matching = [b for b in total_by_bot.keys() if pattern in b.lower()]
        if matching:
            print(f"   '{pattern}' -> {matching} ✅")
        else:
            print(f"   '{pattern}' -> Not seen ❌")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Claude crawler behavior for a GEO domain'
    )
    parser.add_argument(
        '--domain', '-d',
        help='Domain to analyze (e.g., genymotion.com)'
    )
    parser.add_argument(
        '--days', '-n',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file for markdown report (default: print to stdout)'
    )
    parser.add_argument(
        '--list-bots',
        action='store_true',
        help='List all bots seen across all domains (ignores --domain)'
    )

    args = parser.parse_args()

    # Initialize analytics
    analytics = GeoAnalytics()

    # List bots mode
    if args.list_bots:
        list_all_bots(analytics, args.days)
        return

    # Domain analysis mode (requires --domain)
    if not args.domain:
        parser.error("--domain is required unless using --list-bots")

    # Get Claude visits
    visits = get_claude_visits(analytics, args.domain, args.days)

    if not visits:
        print(f"\nNo Claude bot visits found for {args.domain} in the last {args.days} days.")
        print(f"Note: Looking for host header 'rozz.{args.domain}'")
        return

    print(f"\nFound {len(visits)} Claude bot visits for {args.domain}")

    # Generate report
    report = generate_report(args.domain, visits, args.days)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")
    else:
        print("\n" + report)


if __name__ == '__main__':
    main()
