import os
import base64
import requests
import tempfile
import zipfile
import shutil
from flask import Flask, request, session, redirect, url_for, render_template_string
from werkzeug.utils import secure_filename
from groq import Groq

# ---------------------------------------------------------------------------
# Configuration & Environment Variables
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")

app = Flask(__name__)
# CRITICAL FOR VERCEL: Use a static environment variable, not urandom!
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret-key-for-local")

# ---------------------------------------------------------------------------
# Inline HTML Template
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Data Project Analyzer & Publisher</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        .btn { display: inline-block; padding: 10px 15px; margin: 5px 0; color: white; text-decoration: none; border-radius: 5px; }
        .github { background-color: #333; }
        .linkedin { background-color: #0077b5; }
        .submit { background-color: #28a745; border: none; cursor: pointer; font-size: 16px; margin-top: 10px; }
        input[type="text"], input[type="file"] { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;}
        .status { padding: 10px; margin-bottom: 15px; border-radius: 4px; background: #e9ecef; }
    </style>
</head>
<body>
    <h2>Data Project Analyzer & Publisher</h2>
    
    <div class="status">
        <strong>Status:</strong><br>
        GitHub: {% if github_connected %}✅ Connected{% else %}❌ <a href="/login/github" class="btn github">Connect GitHub</a>{% endif %}<br>
        LinkedIn: {% if linkedin_connected %}✅ Connected{% else %}❌ <a href="/login/linkedin" class="btn linkedin">Connect LinkedIn</a>{% endif %}
    </div>

    {% if github_connected and linkedin_connected %}
    <form action="/analyze-and-share" method="POST" enctype="multipart/form-data">
        <label><strong>Upload Project (.zip file):</strong></label><br>
        <input type="file" name="project_zip" accept=".zip" required>
        
        <label><strong>New GitHub Repository Name:</strong></label><br>
        <input type="text" name="repo_name" placeholder="my-data-analysis-project" required>
        
        <button type="submit" class="btn submit">Analyze, Upload & Post</button>
    </form>
    {% else %}
    <p><em>Please connect both accounts to proceed.</em></p>
    {% endif %}

    {% if message %}
    <div style="margin-top:20px; padding: 15px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px;">
        {{ message | safe }}
    </div>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    github_connected = 'github_token' in session
    linkedin_connected = 'linkedin_token' in session
    message = request.args.get('message')
    return render_template_string(HTML_TEMPLATE, 
                                  github_connected=github_connected, 
                                  linkedin_connected=linkedin_connected,
                                  message=message)

# --- GitHub OAuth ---
@app.route('/login/github')
def login_github():
    # Vercel gives us the host URL via the request object, so callbacks are dynamic
    callback_url = request.host_url.rstrip('/') + "/callback/github"
    url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo&redirect_uri={callback_url}"
    return redirect(url)

@app.route('/callback/github')
def callback_github():
    code = request.args.get('code')
    response = requests.post("https://github.com/login/oauth/access_token", 
                             data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code},
                             headers={"Accept": "application/json"})
    session['github_token'] = response.json().get('access_token')
    return redirect(url_for('index'))

# --- LinkedIn OAuth ---
@app.route('/login/linkedin')
def login_linkedin():
    callback_url = request.host_url.rstrip('/') + "/callback/linkedin"
    scope = "openid profile email w_member_social"
    url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={LINKEDIN_CLIENT_ID}&redirect_uri={callback_url}&scope={scope}"
    return redirect(url)

@app.route('/callback/linkedin')
def callback_linkedin():
    code = request.args.get('code')
    callback_url = request.host_url.rstrip('/') + "/callback/linkedin"
    response = requests.post("https://www.linkedin.com/oauth/v2/accessToken",
                             data={"grant_type": "authorization_code", "code": code, 
                                   "client_id": LINKEDIN_CLIENT_ID, "client_secret": LINKEDIN_CLIENT_SECRET, 
                                   "redirect_uri": callback_url})
    session['linkedin_token'] = response.json().get('access_token')
    return redirect(url_for('index'))

# --- Main Logic: Extract, Analyze, Upload, Post ---
@app.route('/analyze-and-share', methods=['POST'])
def analyze_and_share():
    if 'project_zip' not in request.files:
        return redirect(url_for('index', message="No file uploaded!"))
        
    zip_file = request.files['project_zip']
    repo_name = request.form.get('repo_name')
    
    if zip_file.filename == '':
        return redirect(url_for('index', message="Empty file submitted!"))

    code_context = ""
    file_payloads = []
    
    # Create a temporary directory that Vercel allows us to write to
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save and extract the zip file
        zip_path = os.path.join(temp_dir, secure_filename(zip_file.filename))
        zip_file.save(zip_path)
        
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Walk through the extracted files
        for root, dirs, files in os.walk(extract_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', 'node_modules', '__pycache__', 'env']]
            for file in files:
                if not file.startswith('.'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, extract_dir)
                    normalized_path = rel_path.replace("\\", "/")
                    
                    if file.lower().endswith('.pbix'):
                        try:
                            with open(file_path, 'rb') as f:
                                binary_content = f.read()
                            code_context += f"\n--- File Meta: {normalized_path} ---\n[CRITICAL CONTEXT: This file is a functional, interactive Power BI Dashboard file. Highlight its inclusion prominently.]\n"
                            file_payloads.append({"path": normalized_path, "content": base64.b64encode(binary_content).decode('utf-8')})
                        except Exception as e:
                            print(f"Error reading pbix: {e}")
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            if len(code_context) < 15000: 
                                code_context += f"\n--- File: {normalized_path} ---\n{content[:2000]}\n"
                            file_payloads.append({"path": normalized_path, "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')})
                        except Exception:
                            try:
                                with open(file_path, 'rb') as f:
                                    b_content = f.read()
                                file_payloads.append({"path": normalized_path, "content": base64.b64encode(b_content).decode('utf-8')})
                            except Exception:
                                pass

        # 2. Analyze with Groq API
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt_linkedin = f"""You are an expert data analyst and a viral tech influencer on LinkedIn. Analyze the following project files and context, then write a highly engaging, visually stunning LinkedIn post announcing this project. Focus on:
        1. A powerful, scroll-stopping hook at the top highlighting the data insights.
        2. The complete tech stack (including Dataset structure and Power BI).
        3. Core problem solved and key metrics.
        4. Call-to-action to check the GitHub repository.
        Use emojis, line breaks, and hashtags. Output only the raw post.
        Project Context: {code_context}"""
        
        completion_li = client.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role": "user", "content": prompt_linkedin}])
        linkedin_post_content = completion_li.choices[0].message.content.strip()

        prompt_readme = f"""You are a professional data visualization engineer. Write a highly attractive, comprehensive README.md for this repository. Include:
        - Title & Overview
        - 📊 Dashboard Insights & Features (Detail the Power BI report based on context).
        - 📁 Dataset Description
        - 🛠️ Tech Stack
        - ⚙️ Setup Instructions
        Use Markdown styling. Output strictly raw Markdown.
        Project Context: {code_context}"""
        
        try:
            completion_readme = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": prompt_readme}])
            readme_content = completion_readme.choices[0].message.content.strip()
            file_payloads.append({"path": "README.md", "content": base64.b64encode(readme_content.encode('utf-8')).decode('utf-8')})
        except Exception as e:
            print(f"Readme error: {e}")

        # 3. GitHub Upload
        gh_headers = {"Authorization": f"token {session['github_token']}", "Accept": "application/vnd.github.v3+json"}
        github_username = requests.get("https://api.github.com/user", headers=gh_headers).json().get("login")
        
        repo_res = requests.post("https://api.github.com/user/repos", headers=gh_headers, json={"name": repo_name, "private": False})
        repo_url = repo_res.json().get("html_url")

        for f_data in file_payloads:
            requests.put(f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{f_data['path']}", headers=gh_headers, json={"message": f"Upload {f_data['path']}", "content": f_data['content']})

        # 4. LinkedIn Post
        li_headers = {"Authorization": f"Bearer {session['linkedin_token']}"}
        linkedin_urn = requests.get("https://api.linkedin.com/v2/userinfo", headers=li_headers).json().get("sub")

        post_payload = {
            "author": f"urn:li:person:{linkedin_urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": linkedin_post_content},
                    "shareMediaCategory": "ARTICLE",
                    "media": [{"status": "READY", "originalUrl": repo_url}]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        requests.post("https://api.linkedin.com/v2/ugcPosts", headers={**li_headers, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}, json=post_payload)

        success_msg = f"<b>Success!</b><br>Repository created: <a href='{repo_url}'>{repo_url}</a><br>LinkedIn Post published!"
        
    finally:
        # Clean up the temporary Vercel directory to prevent memory leaks
        shutil.rmtree(temp_dir, ignore_errors=True)

    return redirect(url_for('index', message=success_msg))

if __name__ == '__main__':
    app.run(port=5000, debug=True)
