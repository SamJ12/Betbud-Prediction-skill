import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# Load keys
TWITTERAPI_IO_KEY = os.getenv("TWITTERAPI_IO_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
BUBBLE_API_KEY = os.getenv("BUBBLE_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

if not all([TWITTERAPI_IO_KEY, ANTHROPIC_API_KEY, RPC_URL, PRIVATE_KEY, BUBBLE_API_KEY, UNSPLASH_ACCESS_KEY]):
    print("ERROR: Missing keys in .env")
    print("Required: TWITTERAPI_IO_KEY, ANTHROPIC_API_KEY, RPC_URL, PRIVATE_KEY, BUBBLE_API_KEY, UNSPLASH_ACCESS_KEY")
    exit(1)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Contract
CONTRACT_ADDRESS = "0x5bD295b337911160b1Abcba7AFca93D941c1e839"
CONTRACT_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "durationInDays", "type": "uint256"}],
        "name": "openNewMarket",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "currentMarketNumber",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "minimumDeposit",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print("ERROR: Cannot connect to RPC")
    exit(1)

account = w3.eth.account.from_key(PRIVATE_KEY)
contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)

# Bubble - PRODUCTION VERSION
BUBBLE_ROOT = "https://betbud.live/api/1.1/obj"  # CHANGED FROM version-test to production!
DATA_TYPE = "Events"

# Cache file for recent predictions
CACHE_FILE = "recent_predictions.json"

# High-quality crypto Twitter accounts to monitor
PREMIUM_ACCOUNTS = [
    "WatcherGuru",      # Breaking crypto news
    "tier10k",          # Crypto alpha & news
    "CoinDesk",         # Major crypto news outlet
    "Cointelegraph",    # Crypto news
    "TheBlock__",       # Crypto/blockchain news
]

def load_recent_predictions():
    """Load recent predictions from cache to avoid duplicates"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                print(f"✓ Loaded {len(data)} recent predictions from cache")
                return data
    except Exception as e:
        print(f"⚠ Could not load cache: {e}")
    return []

def save_prediction(question):
    """Save a new prediction to cache (keep last 50)"""
    try:
        recent = load_recent_predictions()
        recent.append({
            "question": question,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 50
        recent = recent[-50:]
        with open(CACHE_FILE, 'w') as f:
            json.dump(recent, f, indent=2)
        print(f"✓ Saved to cache (now {len(recent)} total)")
    except Exception as e:
        print(f"⚠ Could not save to cache: {e}")

def fetch_from_accounts(accounts, tweets_per_account=3):
    """Fetch recent tweets from specific Twitter accounts"""
    all_tweets = []
    
    for account in accounts:
        try:
            # Search for tweets FROM this account in last 2 days
            since = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            query = f"from:{account} -filter:replies -filter:retweets since:{since}"
            
            url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
            headers = {"x-api-key": TWITTERAPI_IO_KEY}
            params = {"query": query, "count": tweets_per_account}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            tweets = data.get('tweets', []) or data.get('data', [])
            if tweets:
                print(f"  ✓ {account}: {len(tweets)} tweets")
                all_tweets.extend(tweets)
            else:
                print(f"  ⚠ {account}: No tweets")
                
        except Exception as e:
            print(f"  ✗ {account}: {str(e)[:50]}")
    
    return all_tweets

def fetch_trending_topics(category="crypto", limit=5):
    """Fetch trending crypto topics (reduced limit to save tokens)"""
    since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")  # Only 1 day for freshness
    query = f"{category} (breaking OR announced OR launch) min_faves:200 since:{since}"
    
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    headers = {"x-api-key": TWITTERAPI_IO_KEY}
    params = {"query": query, "count": limit}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        tweets = data.get('tweets', []) or data.get('data', [])
        print(f"  ✓ Trending: {len(tweets)} tweets")
        return tweets
    except Exception as e:
        print(f"  ✗ Trending: {str(e)}")
        return []

def get_diverse_content():
    """Fetch diverse content from both accounts and trending topics"""
    print("\n=== Fetching Content ===")
    
    # Get tweets from premium accounts (3 each = ~15 tweets)
    print("📱 Fetching from premium accounts:")
    account_tweets = fetch_from_accounts(PREMIUM_ACCOUNTS, tweets_per_account=3)
    
    # Get trending topics (5 tweets)
    print("🔥 Fetching trending topics:")
    trending_tweets = fetch_trending_topics(limit=5)
    
    # Combine and deduplicate
    all_tweets = account_tweets + trending_tweets
    
    # Remove duplicates by tweet ID
    seen_ids = set()
    unique_tweets = []
    for tweet in all_tweets:
        tweet_id = tweet.get('id') or tweet.get('tweet_id')
        if tweet_id and tweet_id not in seen_ids:
            seen_ids.add(tweet_id)
            unique_tweets.append(tweet)
    
    print(f"\n✓ Total unique tweets: {len(unique_tweets)}")
    return unique_tweets

def extract_keywords_from_question(question):
    """Extract main keywords from prediction question for image search"""
    # Remove common prediction market words
    question_lower = question.lower()
    
    # Remove common phrases
    remove_phrases = [
        "will ", "by ", "happen", "reach", "announce", "the ", "a ", "an ",
        "prediction", "market", "?", "2026", "2025", "2024"
    ]
    
    for phrase in remove_phrases:
        question_lower = question_lower.replace(phrase, " ")
    
    # Clean up
    keywords = question_lower.strip()
    
    # Get first 2-3 meaningful words
    words = [w for w in keywords.split() if len(w) > 3][:3]
    
    return " ".join(words) if words else "cryptocurrency"

def get_professional_image(question, category="Crypto"):
    """Fetch professional image from Unsplash based on prediction question"""
    print(f"\n=== Fetching Professional Image ===")
    
    # Extract keywords from question
    keywords = extract_keywords_from_question(question)
    
    # Add category-specific terms to improve relevance
    category_keywords = {
        "Crypto": "cryptocurrency bitcoin blockchain",
        "Price": "stock market trading finance",
        "Politics": "politics government capitol",
        "Elections": "voting election democracy",
        "Sport": "sports competition athlete",
        "Gaming": "gaming esports video game",
        "Tech": "technology innovation digital",
        "People": "people crowd community",
        "music": "music concert performance",
        "Pop": "entertainment celebrity culture",
    }
    
    # Combine extracted keywords with category context
    search_query = f"{keywords} {category_keywords.get(category, 'news')}"
    
    print(f"  Searching Unsplash for: '{search_query}'")
    
    try:
        # Unsplash API endpoint
        url = "https://api.unsplash.com/search/photos"
        headers = {
            "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
        }
        params = {
            "query": search_query,
            "per_page": 1,
            "orientation": "landscape",  # Better for cards/previews
            "content_filter": "high"      # Filter out low-quality images
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('results') and len(data['results']) > 0:
            image = data['results'][0]
            image_url = image['urls']['regular']  # High quality but not huge
            photographer = image['user']['name']
            
            print(f"  ✓ Found image by {photographer}")
            print(f"  URL: {image_url[:60]}...")
            
            return image_url
        else:
            print(f"  ⚠ No results, using fallback")
            # Fallback to generic crypto image
            return get_fallback_image(category)
            
    except Exception as e:
        print(f"  ✗ Unsplash error: {str(e)[:100]}")
        return get_fallback_image(category)

def get_fallback_image(category):
    """Get a fallback image if Unsplash fails"""
    # Hardcoded fallback searches that always work
    fallback_queries = {
        "Crypto": "cryptocurrency",
        "Price": "stock market",
        "Politics": "politics",
        "Elections": "voting",
        "Sport": "sports",
        "Gaming": "gaming",
        "Tech": "technology",
        "music": "music",
        "Pop": "entertainment",
    }
    
    query = fallback_queries.get(category, "news")
    
    try:
        url = "https://api.unsplash.com/photos/random"
        headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        params = {"query": query, "orientation": "landscape"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return data['urls']['regular']
    except:
        # Ultimate fallback - empty string (Bubble will handle it)
        return ""

def analyze_with_claude(tweets, recent_predictions):
    """Use Claude to pick a UNIQUE topic and create prediction market"""
    if not tweets:
        raise ValueError("No tweets found")
    
    # Build list of recent topics to avoid
    recent_topics = [p['question'] for p in recent_predictions[-10:]]  # Last 10 only
    recent_topics_str = "\n".join([f"- {q}" for q in recent_topics]) if recent_topics else "None"
    
    prompt = f"""You are analyzing crypto Twitter to find the BEST prediction market opportunity.

RECENT PREDICTIONS (AVOID THESE TOPICS):
{recent_topics_str}

AVAILABLE TWEETS:
{json.dumps(tweets[:10], default=str)}

YOUR TASK:
1. Find a topic that is DIFFERENT from recent predictions
2. Pick something SPECIFIC and TIME-BOUND
3. Avoid vague regulatory deadlines unless there's a new angle
4. Look for: product launches, price predictions, merger announcements, tech releases, specific events

Create a yes/no prediction market proposal in valid JSON:
{{
  "question": "Will [SPECIFIC event] happen by [SPECIFIC date]?",
  "duration_days": 7,
  "category": "Crypto",
  "resolution_criteria": "Clear resolution method with sources",
  "score": 8.0-10.0,
  "reasoning": "Why this is unique and interesting",
  "sources": ["https://source1.com", "https://source2.com"]
}}

CRITICAL: Make the question DIFFERENT from recent predictions. Look for NEW developments.
Valid categories: Politics, Elections, Sport, Gaming, Crypto, Price, Tech, People, Personal, music, Pop, other

Return ONLY the JSON object. No markdown, no extra text."""
    
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = message.content[0].text.strip()
        
        # Strip markdown
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        
        # Extract JSON
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            text = text[start:end]
        
        proposal = json.loads(text)
        
        # Validate required fields
        if "question" not in proposal:
            raise ValueError("Missing question field")
        
        # Add defaults
        proposal.setdefault("category", "Crypto")
        proposal.setdefault("duration_days", 7)
        
        print(f"\n✓ Claude generated: {proposal['question'][:80]}...")
        return proposal
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse error: {e}")
        print(f"Text: {text[:200]}")
        raise
    except Exception as e:
        print(f"✗ Claude error: {e}")
        raise

def get_min_deposit():
    try:
        min_wei = contract.functions.minimumDeposit().call()
        min_eth = w3.from_wei(min_wei, 'ether')
        print(f"✓ Min deposit: {min_eth} ETH")
        return min_wei
    except Exception as e:
        print(f"⚠ Error: {e}")
        return w3.to_wei(0.0001, 'ether')

def create_market(duration_days):
    print(f"\n=== Creating Blockchain Market ===")
    min_deposit = get_min_deposit()
    current_num = contract.functions.currentMarketNumber().call()
    new_num = current_num + 1
    
    print(f"  Market #{new_num}, Duration: {duration_days} days")
    
    try:
        tx = contract.functions.openNewMarket(duration_days).build_transaction({
            'from': account.address,
            'value': min_deposit,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'maxFeePerGas': w3.to_wei('2', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('1', 'gwei'),
        })
        
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"  TX sent: {tx_hash.hex()[:20]}...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            explorer = f"https://sepolia.basescan.org/tx/{tx_hash.hex()}"
            print(f"✓ Market #{new_num} created!")
            print(f"  {explorer}")
            return new_num, tx_hash.hex(), explorer
        else:
            print("✗ TX failed")
            return None, None, None
    except Exception as e:
        print(f"✗ Error: {str(e)[:100]}")
        return None, None, None

def register_bubble_event(proposal, market_num, creator_wallet, image_url):
    print(f"\n=== Registering to Bubble.io PRODUCTION ===")
    
    url = f"{BUBBLE_ROOT}/{DATA_TYPE}"
    headers = {
        "Authorization": f"Bearer {BUBBLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    valid_cats = ["Politics", "Elections", "Sport", "Gaming", "Crypto", "Price", 
                  "Tech", "People", "Personal", "music", "Pop", "other"]
    cat = proposal.get("category", "Crypto")
    if cat not in valid_cats:
        cat = "other"
    
    # Use DISPLAY field names (not API IDs) - this is what works!
    data = {
        "tittle": proposal.get("question", "No title"),
        "rules": proposal.get("resolution_criteria", "No rules"),
        "duration ( days ) ": int(proposal.get("duration_days", 7)),
        "category": cat,
        "walletID-event-creator": creator_wallet,
        "Event number": int(market_num),
        "closed?": False,
        "overrided ? ": False,
        "rewardClaimed?": False,
        "privacy": "public",
        "Reward amount": 0,
        "final outcome": "",
        "OUTCOME": "",
        "event Preview URL ": "",
        "image": image_url  # Professional image from Unsplash!
    }
    
    print(f"  URL: {url}")
    print(f"  Market #: {market_num}")
    print(f"  Image: {image_url[:50]}..." if image_url else "  No image")
    
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        
        if resp.status_code in [200, 201]:
            print(f"✓ Registered to PRODUCTION Bubble.io!")
            try:
                response_data = resp.json()
                print(f"  Response: {response_data}")
            except:
                print(f"  Response: {resp.text[:200]}")
            return True
        else:
            print(f"✗ Bubble error: {resp.status_code}")
            print(f"  {resp.text[:300]}")
            return False
            
    except Exception as e:
        print(f"✗ Exception: {str(e)[:100]}")
        return False

def main():
    print("\n" + "="*60)
    print("  PRODUCTION PREDICTION MARKET CREATOR")
    print("  → betbud.live (LIVE APP)")
    print("="*60)
    
    # Load recent predictions to avoid duplicates
    recent_predictions = load_recent_predictions()
    
    # Fetch diverse content (accounts + trending)
    tweets = get_diverse_content()
    
    if not tweets:
        print("\n✗ No tweets found. Exiting.")
        return
    
    # Analyze with Claude (passing recent predictions to avoid duplicates)
    print("\n=== Analyzing with Claude ===")
    try:
        proposal = analyze_with_claude(tweets, recent_predictions)
        
        print(f"\n📋 Proposal:")
        print(f"  Q: {proposal['question']}")
        print(f"  Category: {proposal.get('category', 'N/A')}")
        print(f"  Duration: {proposal.get('duration_days', 'N/A')} days")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return
    
    # Get professional image for this prediction
    image_url = get_professional_image(proposal['question'], proposal.get('category', 'Crypto'))
    
    # Create blockchain market
    market_num, tx_hash, explorer = create_market(proposal["duration_days"])
    
    if not market_num:
        print("✗ Blockchain creation failed. Exiting.")
        return
    
    # Register to PRODUCTION Bubble with image
    success = register_bubble_event(proposal, market_num, account.address, image_url)
    
    # Save to cache if successful
    if success:
        save_prediction(proposal['question'])
    
    # Final summary
    print("\n" + "="*60)
    print("  PRODUCTION SUMMARY")
    print("="*60)
    print(f"Question: {proposal['question']}")
    print(f"Market #: {market_num}")
    print(f"Category: {proposal.get('category', 'N/A')}")
    print(f"Image: {image_url[:50]}..." if image_url else "No image")
    print(f"TX: {tx_hash}")
    print(f"Live App: {'✓ SUCCESS - LIVE ON BETBUD.LIVE!' if success else '✗ Failed'}")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted")
    except Exception as e:
        print(f"\n✗ FATAL: {str(e)}")
        import traceback
        traceback.print_exc()