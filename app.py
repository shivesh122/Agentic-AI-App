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
        prompt_linkedin = f"""
    You are an expert developer and a viral tech influencer on LinkedIn. Analyze the following project files and write a highly engaging, visually attractive LinkedIn post announcing this project. 
    Focus on:
    1. A strong, scroll-stopping hook at the beginning.
    2. The technical stack (use appropriate emojis for the tech).
    3. The core problem it solves and its key features (use bullet points or checkmarks).
    4. A clear Call-to-Action (asking for feedback or to check out the GitHub repo).
    Use plenty of appropriate emojis, line breaks for readability, and relevant tech hashtags. Do not include introductory/outro text, just the raw post.
    
    Project Files Context:
    {code_context}
    """
    completion_li = client.chat.completions.create(
        model="openai/gpt-oss-20b", # Switched to Llama 3 70B for better formatting and writing
        messages=[{"role": "user", "content": prompt_linkedin}],
    )
    linkedin_post_content = completion_li.choices[0].message.content.strip()

    # 2b. Generate Attractive README.md
    prompt_readme = f"""
    You are an expert developer and technical writer. Analyze the following project files and write a highly attractive, comprehensive, and professional README.md for this repository.
    Include the following sections:
    - A catchy Title and short description.
    - 🚀 Features section (bullet points).
    - 🛠️ Tech Stack section.
    - 💻 Setup and Installation instructions.
    - 🎯 Usage guide.
    Use markdown formatting extensively (bold, headers, lists, code blocks) to make it visually appealing. Output strictly the raw Markdown content. Do not include markdown code block backticks (```) at the beginning or end of your entire response.
    
    Project Files Context:
    {code_context}
    """
    try:
        completion_readme = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt_readme}],
        )
        readme_content = completion_readme.choices[0].message.content.strip()
        
        # Add the AI-generated README to the files to be uploaded
        file_payloads.append({
            "path": "README.md",
            "content": base64.b64encode(readme_content.encode('utf-8')).decode('utf-8')
        })
    except Exception as e:
        print(f"Groq API Error generating README: {e}")

    # 3. Create GitHub Repo & Upload Files
    gh_headers = {
        "Authorization": f"token {session['github_token']}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Create repo
    gh_user_res = requests.get("https://api.github.com/user", headers=gh_headers).json()
    github_username = gh_user_res.get("login")
    
    repo_res = requests.post("https://api.github.com/user/repos", headers=gh_headers, json={"name": repo_name, "private": False})
    repo_url = repo_res.json().get("html_url")

    # Upload files to GitHub via API
    for f_data in file_payloads:
        put_url = f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{f_data['path']}"
        requests.put(put_url, headers=gh_headers, json={
            "message": f"Initial commit: {f_data['path']}",
            "content": f_data['content']
        })

    # 4. Post to LinkedIn
    li_headers = {"Authorization": f"Bearer {session['linkedin_token']}"}
    
    # Get LinkedIn user ID (sub)
    userinfo_res = requests.get("https://api.linkedin.com/v2/userinfo", headers=li_headers).json()
    linkedin_urn = userinfo_res.get("sub")

    # Construct the UGC Post
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
    
    li_post_res = requests.post("https://api.linkedin.com/v2/ugcPosts", headers={**li_headers, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}, json=post_payload)

    success_msg = f"<b>Success!</b><br>Repository created (with an attractive README!): <a href='{repo_url}' target='_blank'>{repo_url}</a><br>Engaging LinkedIn Post drafted and published!"
    return redirect(url_for('index', message=success_msg))

if __name__ == '__main__':
    # Run locally on port 5000
    app.run(port=5000, debug=True)
