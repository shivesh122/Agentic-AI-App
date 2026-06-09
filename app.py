import os
import base64
import requests
import tempfile
import zipfile
import shutil
import traceback
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
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret-key-for-local")

# ---------------------------------------------------------------------------
# Upgraded Modern HTML Template with Loading UI
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Portfolio Publisher</title>
    <style>
        :root { --primary: #2563eb; --success: #16a34a; --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --border: #e2e8f0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg); color: var(--text); display: flex; justify-content: center; padding: 40px 20px; margin: 0; }
        .container { background: var(--card); max-width: 650px; width: 100%; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); padding: 30px; border: 1px solid var(--border); }
        h2 { text-align: center; margin-top: 0; color: #0f172a; font-weight: 700; font-size: 24px; }
        p.subtitle { text-align: center; color: #64748b; margin-bottom: 30px; font-size: 14px; }
        
        .status-board { display: flex; gap: 15px; margin-bottom: 25px; }
        .status-card { flex: 1; padding: 15px; border-radius: 8px; border: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: #fdfdfd; }
        .btn { padding: 10px 16px; font-weight: 600; text-decoration: none; border-radius: 6px; font-size: 14px; transition: all 0.2s; text-align: center; cursor: pointer; border: none; }
        .btn-github { background-color: #24292e; color: white; }
        .btn-github:hover { background-color: #1b1f23; }
        .btn-linkedin { background-color: #0a66c2; color: white; }
        .btn-linkedin:hover { background-color: #004182; }
        .btn-submit { background-color: var(--primary); color: white; width: 100%; padding: 14px; font-size: 16px; margin-top: 10px; }
        .btn-submit:hover { background-color: #1d4ed8; }
        .btn-submit:disabled { background-color: #94a3b8; cursor: not-allowed; }
        
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; font-size: 14px; color: #334155; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 6px; box-sizing: border-box; font-size: 14px; transition: border 0.2s; }
        input[type="text"]:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
        
        .file-upload { border: 2px dashed #cbd5e1; border-radius: 8px; padding: 25px; text-align: center; background: #f8fafc; transition: all 0.2s; cursor: pointer; position: relative;}
        .file-upload:hover { border-color: var(--primary); background: #f1f5f9; }
        .file-upload input[type="file"] { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
        .file-icon { font-size: 30px; margin-bottom: 10px; display: block; }
        
        .alert { padding: 16px; border-radius: 8px; margin-top: 20px; font-size: 14px; line-height: 1.5; }
        .alert-success { background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
        .alert-error { background-color: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
        
        #loading-overlay { display: none; margin-top: 20px; text-align: center; padding: 20px; border-radius: 8px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a;}
        .spinner { display: inline-block; width: 24px; height: 24px; border: 3px solid rgba(37, 99, 235, 0.3); border-radius: 50%; border-top-color: var(--primary); animation: spin 1s ease-in-out infinite; margin-bottom: 10px;}
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h2>🚀 AI Project Publisher</h2>
        <p class="subtitle">Instantly analyze your code, write an HR-ready README, and post to LinkedIn.</p>
        
        <div class="status-board">
            <div class="status-card">
                <span><img src="https://github.githubassets.com/favicons/favicon.svg" width="16" style="vertical-align: middle; margin-right: 5px;"> GitHub</span>
                {% if github_connected %}<span style="color: var(--success); font-weight:bold;">✓ Connected</span>{% else %}<a href="/login/github" class="btn btn-github">Connect</a>{% endif %}
            </div>
            <div class="status-card">
                <span><img src="https://static.licdn.com/aero-v1/sc/h/al2o9zrvru7aqj8e1x2rzsrca" width="16" style="vertical-align: middle; margin-right: 5px;"> LinkedIn</span>
                {% if linkedin_connected %}<span style="color: var(--success); font-weight:bold;">✓ Connected</span>{% else %}<a href="/login/linkedin" class="btn btn-linkedin">Connect</a>{% endif %}
            </div>
        </div>

        {% if github_connected and linkedin_connected %}
        <form action="/analyze-and-share" method="POST" enctype="multipart/form-data" id="uploadForm">
            
            <div class="form-group">
                <label>Repository Name (No spaces)</label>
                <input type="text" name="repo_name" placeholder="e.g., ai-portfolio-generator" pattern="[a-zA-Z0-9-_]+" required>
            </div>

            <div class="form-group">
                <label>Upload Project (.zip format)</label>
                <div class="file-upload">
                    <span class="file-icon">📁</span>
                    <span id="file-name">Drag & drop your .zip file here, or click to browse</span>
                    <br><small style="color: #64748b;">Max size: 4.5MB (Vercel Limit)</small>
                    <input type="file" name="project_zip" accept=".zip" required onchange="document.getElementById('file-name').innerHTML = '<b>' + this.files[0].name + '</b> selected';">
                </div>
            </div>
            
            <button type="submit" class="btn btn-submit" id="submitBtn">Analyze & Publish</button>
            
            <div id="loading-overlay">
                <div class="spinner"></div>
                <div style="font-weight: 600;">AI is analyzing your project...</div>
                <div style="font-size: 13px; margin-top: 5px;">Extracting files, calling Groq LLM, writing README, and publishing.<br>This usually takes 15-30 seconds. Please do not refresh.</div>
            </div>
        </form>
        
        <script>
            document.getElementById('uploadForm').onsubmit = function() {
                document.getElementById('submitBtn').style.display = 'none';
                document.getElementById('loading-overlay').style.display = 'block';
            };
        </script>
        {% else %}
        <div style="text-align: center; padding: 30px; background: #f8fafc; border-radius: 8px; border: 1px dashed var(--border);">
            <span style="font-size: 24px;">🔒</span><br><br>
            <em style="color: #64748b;">Please connect both your GitHub and LinkedIn accounts above to unlock the publishing engine.</em>
        </div>
        {% endif %}

        {% if message %}
        <div class="alert {% if 'Crash' in message or 'Error' in message or 'Failed' in message %}alert-error{% else %}alert-success{% endif %}">
            {{ message | safe }}
        </div>
        {% endif %}
    </div>
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
    try:
        if 'project_zip' not in request.files:
            return redirect(url_for('index', message="Error: No file uploaded!"))
            
        zip_file = request.files['project_zip']
        repo_name = request.form.get('repo_name')
        
        if zip_file.filename == '':
            return redirect(url_for('index', message="Error: Empty file submitted!"))

        code_context = ""
        file_payloads = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Save and extract zip
            zip_path = os.path.join(temp_dir, secure_filename(zip_file.filename))
            zip_file.save(zip_path)
            
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Process extracted files generically
            for root, dirs, files in os.walk(extract_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', 'node_modules', '__pycache__', 'env', '.git']]
                for file in files:
                    if not file.startswith('.'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, extract_dir)
                        normalized_path = rel_path.replace("\\", "/")
                        
                        # Try reading as text to give to AI
                        is_text = False
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                is_text = True
                                # Add up to 15k chars to AI context
                                if len(code_context) < 15000: 
                                    code_context += f"\n--- File: {normalized_path} ---\n{content[:2000]}\n"
                        except UnicodeDecodeError:
                            # It's a binary file (image, pbix, pdf, compiled code). 
                            # Tell AI it exists, but don't paste the gibberish.
                            if len(code_context) < 15000:
                                code_context += f"\n--- File Meta: {normalized_path} ---\n[CONTEXT: Binary/Media file present in architecture.]\n"
                        
                        # Prepare file for GitHub Upload (Read as bytes for safety)
                        with open(file_path, 'rb') as f:
                            b_content = f.read()
                        file_payloads.append({
                            "path": normalized_path, 
                            "content": base64.b64encode(b_content).decode('utf-8')
                        })

            # Initialize Groq
            client = Groq(api_key=GROQ_API_KEY)
            
            # --- AI TASK 1: LinkedIn Viral & Professional Post ---
            prompt_linkedin = f"""You are an elite AIML Developer and Data Analyst sharing your latest project on LinkedIn. Write a highly attractive, viral, and professional post.
            
            Strict Rules for Formatting & Style:
            1. BOLD TEXT: LinkedIn does not support markdown (**). You MUST use Unicode bold characters (e.g., 𝗯𝗼𝗹𝗱 𝘁𝗲𝘅𝘁) for your section headers and most important keywords so they stand out.
            2. EMOJIS: Use a rich variety of professional emojis (🚀, 📊, 🧠, 💡, 🛠️, 📈) to structure the post and act as visual bullet points. Do not hold back on emojis; make it highly scannable.
            3. STRUCTURE:
               - 𝗛𝗼𝗼𝗸: A scroll-stopping opening statement about the value of this project.
               - 𝗧𝗵𝗲 𝗣𝗿𝗼𝗯𝗹𝗲𝗺: What challenge does this solve?
               - 𝗧𝗵𝗲 𝗦𝗼𝗹𝘂𝘁𝗶𝗼𝗻 & 𝗜𝗻𝘀𝗶𝗴𝗵𝘁𝘀: Highlight 2-3 impressive metrics, features, or dashboard capabilities.
               - 𝗧𝗲𝗰𝗵 𝗦𝘁𝗮𝗰𝗸: List the tools used with distinct emojis.
            4. VISUAL CONTEXT: A rich visual preview card of the GitHub repository will automatically attach to this post. Make sure to tell the reader to "check out the code and dashboard in the link below 👇".
            5. CTA: End with an engaging question for your network to drive comments.
            
            Output ONLY the raw post content. Do not include any conversational filler or introductions.
            Project Context: {code_context}"""
            
            completion_li = client.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role": "user", "content": prompt_linkedin}])
            linkedin_post_content = completion_li.choices[0].message.content.strip()

            # --- AI TASK 2: DevRel Grade README ---
            prompt_readme = f"""You are a top-tier Developer Advocate. Write a world-class, highly attractive README.md for this repository.
            Must Include:
            - A catchy Title and 1-sentence tag-line.
            - Markdown Badges representing the tech stack (e.g., `![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)`). Infer the tech stack from the code.
            - 🎯 **Why This Project Exists** (Business or technical value - highly attractive to HR).
            - 🚀 **Key Features** (Bullet points).
            - 🏗️ **Architecture / Tech Stack Overview**.
            - 💻 **Getting Started / Installation**.
            Output STRICTLY raw Markdown. Do not enclose in ```markdown backticks.
            Project Context: {code_context}"""
            
            completion_readme = client.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role": "user", "content": prompt_readme}])
            readme_content = completion_readme.choices[0].message.content.strip()
            
            # Strip backticks if the model ignores instructions
            if readme_content.startswith("```"):
                readme_content = "\n".join(readme_content.split("\n")[1:-1])

            file_payloads.append({"path": "README.md", "content": base64.b64encode(readme_content.encode('utf-8')).decode('utf-8')})

            # --- AI TASK 3: The "HR Elevator Pitch" (New Feature) ---
            prompt_pitch = f"""You are an elite Technical Recruiter. Based on this project, write a 3-bullet-point 'Elevator Pitch' that the developer can copy-paste directly onto their Resume or Personal Portfolio website under the 'Projects' section. 
            Focus strictly on action verbs, technical implementation, and implied results. Make it sound highly impressive to a hiring manager.
            Output ONLY the 3 bullet points.
            Project Context: {code_context}"""
            
            completion_pitch = client.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role": "user", "content": prompt_pitch}])
            pitch_content = "### RESUME / PORTFOLIO BULLET POINTS\n\n" + completion_pitch.choices[0].message.content.strip()
            file_payloads.append({"path": "HR_ELEVATOR_PITCH.txt", "content": base64.b64encode(pitch_content.encode('utf-8')).decode('utf-8')})

            # --- GitHub Upload ---
            gh_headers = {"Authorization": f"token {session['github_token']}", "Accept": "application/vnd.github.v3+json"}
            github_username = requests.get("https://api.github.com/user", headers=gh_headers).json().get("login")
            
            repo_res = requests.post("https://api.github.com/user/repos", headers=gh_headers, json={
                "name": repo_name, 
                "private": False,
                "description": "Project analyzed and deployed via AI Portfolio Generator"
            })
            if repo_res.status_code not in [200, 201]:
                raise Exception(f"GitHub Repo Creation Failed: {repo_res.text}")
            repo_url = repo_res.json().get("html_url")

            # Upload files
            for f_data in file_payloads:
                requests.put(f"https://api.github.com/repos/{github_username}/{repo_name}/contents/{f_data['path']}", headers=gh_headers, json={"message": f"Auto-Commit: {f_data['path']}", "content": f_data['content']})

            # --- LinkedIn Post ---
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
            li_res = requests.post("https://api.linkedin.com/v2/ugcPosts", headers={**li_headers, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}, json=post_payload)
            if li_res.status_code != 201:
                print(f"LinkedIn Post Warning: {li_res.text}")

            success_msg = f"<b>🎉 Boom! Successfully Published.</b><br><br><b>1. GitHub Repo:</b> <a href='{repo_url}' target='_blank'>{repo_url}</a><br><b>2. Resume Elevator Pitch:</b> Generated & saved in your repo.<br><b>3. LinkedIn:</b> Post published to your feed!"
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True) # Always clean up Vercel storage

        return redirect(url_for('index', message=success_msg))

    except Exception as e:
        print("APP CRASHED:", traceback.format_exc())
        error_html = f"<b>System Crash:</b> {str(e)}<br><br>Check Vercel Runtime Logs."
        return redirect(url_for('index', message=error_html))

if __name__ == '__main__':
    app.run(port=5000, debug=True)
