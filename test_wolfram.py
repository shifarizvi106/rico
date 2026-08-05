import requests

# Paste the AppID you are currently using here
APP_ID = "URTVTLXYE9"
query = "50 + 145"

# Construct the API request URL
url = f"http://api.wolframalpha.com/v2/query?input={query}&appid={APP_ID}"

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print("\n--- Headers ---")
    print(response.headers)
    print("\n--- Response Text (The Error Message) ---")
    print(response.text)
except Exception as e:
    print(f"An error occurred: {e}")
