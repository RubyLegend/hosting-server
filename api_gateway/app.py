from flask import Flask, jsonify
import requests
import os
import yaml
import copy
from flasgger import Swagger

app = Flask(__name__)

# Configuration (using environment variables is recommended for production)
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://hosting-user-api:9000")
VIDEO_SERVICE_URL = os.environ.get("VIDEO_SERVICE_URL", "http://hosting-video-api:9000")
COMPANY_SERVICE_URL = os.environ.get("COMPANY_SERVICE_URL", "http://hosting-company-api:9000")
SEARCH_SERVICE_URL = os.environ.get("SEARCH_SERVICE_URL", "http://hosting-search-api:9000")
swagger = Swagger(app)

def deep_merge(dict1, dict2):
    """Recursively merges two dictionaries."""
    result = copy.deepcopy(dict1)
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


def fetch_swagger_spec(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json() if response.headers.get('Content-Type') == 'application/json' else yaml.safe_load(response.text)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching Swagger spec from {url}: {e}")
        return None


@app.route("/apispec_2.json")
def get_swagger_json():
    specs = []
    service_urls = [
        f"{USER_SERVICE_URL}/apispec_1.json",
        f"{VIDEO_SERVICE_URL}/apispec_1.json",
        f"{COMPANY_SERVICE_URL}/apispec_1.json",
        f"{SEARCH_SERVICE_URL}/apispec_1.json",
    ]
    for url in service_urls:
        spec = fetch_swagger_spec(url)
        if spec:
            specs.append(spec)

    merged_spec = specs[0]
    for spec in specs[1:]:
        merged_spec = deep_merge(merged_spec, spec)
    
    merged_spec['info'] = {
        "title": "API Tester",
        "description": "API for testing all endpoints for Media Hosting application",
        "version": "1.0.0"
    }

    return jsonify(merged_spec)

@app.route("/")
def hello():
    return "<h1>Hello</h1>"


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=9000)
