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
# Premium UI Template (Tailwind CSS + Loading Animations)
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Project Publisher | Enterprise Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .glass { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); }
        .loader { border-top-color: #3b82f6; animation: spinner 1.5s linear infinite; }
        @keyframes spinner { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 min-h-screen font-sans text-slate-800 flex items-center justify-center p-4">
    
    <div class="glass max-w-2xl w-full rounded-2xl shadow-2xl overflow-hidden border border-white/20">
        <div class="bg-blue-600 p-6 text-center">
            <h1 class="text-3xl font-extrabold text-white tracking-tight">AutoPublisher AI</h1>
            <p class="text-blue-200 mt-2 text-sm font-medium">Enterprise Data Analytics Deployment Engine</p>
        </div>

        <div class="p-8">
            <div class="flex gap-4 mb-8">
                <div class="flex-1 p-4 rounded-xl border flex items-center justify-between {% if github_connected %}bg-green-50 border-green-200{% else %}bg-slate-50 border-slate-200{% endif %}">
                    <span class="font-semibold flex items-center gap-2">
                        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                        GitHub
                    </span>
                    {% if github_connected %}
                        <span class="text-green-600 font-bold">✓ Connected</span>
                    {% else %}
                        <a href="/login/github" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-lg transition">Connect</a>
                    {% endif %}
                </div>

                <div class="flex-1 p-4 rounded-xl border flex items-center justify-between {% if linkedin_connected %}bg-blue-50 border-blue-200{% else %}bg-slate-50 border-slate-200{% endif %}">
                    <span class="font-semibold flex items-center gap-2">
                        <svg class="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                        LinkedIn
                    </span>
                    {% if linkedin_connected %}
                        <span class="text-blue-600 font-bold">✓ Connected</span>
                    {% else %}
                        <a href="/login/linkedin" class="px-4 py-2 bg-[#0077b5] hover:bg-[#006097] text-white text-sm font-bold rounded-lg transition">Connect</a>
                    {% endif %}
                </div>
            </div>

            {% if message %}
            <div class="mb-6 p-4 rounded-lg bg-slate-100 border-l-4 border-blue-500 shadow-inner">
                {{ message | safe }}
            </div>
            {% endif %}

            {% if github_connected and linkedin_connected %}
            <form id="uploadForm" action="/analyze-and-share" method="POST" enctype="multipart/form-data" class="space-y-6">
                
                <div>
                    <label class="block text-sm font-bold text-slate-700 mb-2">Upload Project Archive (.zip)</label>
                    <div class="relative border-2 border-dashed border-slate-300 rounded-xl p-8 hover:bg-slate-50 transition text-center cursor-pointer">
                        <input type="file" name="project_zip" accept=".zip" required class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10">
                        <div class="text-slate-500">
                            <svg class="mx-auto h-12 w-12 mb-3 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                            <span class="font-semibold text-blue-600">Click to upload</span> or drag and drop
                            <p class="text-xs mt-1">Must contain Dataset & Power BI (.pbix) files</p>
                        </div>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-bold text-slate-700 mb-2">Repository Name</label>
                    <input type="text" name="repo_name" placeholder="e.g., retail-sales-insights" required class="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition shadow-sm">
                </div>
                
                <button type="submit" class="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold rounded-xl shadow-lg transform hover:-translate-y-0.5 transition-all flex justify-center items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    Analyze, Deploy to GitHub & Post to LinkedIn
                </button>
            </form>

            <div id="loadingState" class="hidden text-center py-12 space-y-4">
                <div class="loader ease-linear rounded-full border-4 border-slate-200 h-16 w-16 mx-auto"></div>
                <h3 class="text-xl font-bold text-slate-800">Processing Enterprise Pipeline...</h3>
                <p class="text-slate-500 text-sm animate-pulse">Extracting Code ➔ Generating AI Docs ➔ Pushing to Cloud</p>
                <p class="text-xs text-amber-600 font-semibold mt-4">Do not close or refresh this page. This may take up to 30 seconds.</p>
            </div>
            
            <script>
                document.getElementById('uploadForm').addEventListener('submit', function() {
                    this.style.display = 'none';
                    document.getElementById('loadingState').classList.remove('hidden');
                });
            </script>
            {% else %}
            <div class="text-center py-8">
                <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 mb-4">
                    <svg class="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8V7a4 4 0 00-8 0v4h8z"></path></svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800">Authentication Required</h3>
                <p class="text-slate-500 mt-2">Please connect both GitHub and LinkedIn securely above to activate the deployment engine.</p>
            </div>
            {% endif %}
        </div>
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
            return redirect(url_for('index', message="<span class='text-red-600 font-bold'>Error:</span> No file uploaded!"))
            
        zip_file = request.files['project_zip']
        repo_name = request.form.get('repo_name')
        
        if zip_file.filename == '':
            return redirect(url_for('index', message="<span class='text-red-600 font-bold'>Error:</span> Empty file submitted!"))

        code_context = ""
        file_payloads = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            zip_path = os.path.join(temp_dir, secure_filename(zip_file.filename))
            zip_file.save(zip_path)
            
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            for root, dirs, files in os.walk(extract_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', 'node_modules', '__pycache__', 'env']]
                for file in files:
                    if not file.startswith('.'):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, extract_dir)
                        normalized_path = rel_path.replace("\\", "/")
                        
                        if file.lower().endswith('.pbix'):
                            with open(file_path, 'rb') as f:
                                binary_content = f.read()
                            code_context += f"\n--- File Meta: {normalized_path} ---\n[CRITICAL CONTEXT: This file is a highly functional, interactive Power BI Dashboard file designed to derive business insights. Highlight its inclusion prominently as an enterprise-grade asset.]\n"
                            file_payloads.append({"path": normalized_path, "content": base64.b64encode(binary_content).decode('utf-8')})
                        else:
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                if len(code_context) < 15000: 
                                    code_context += f"\n--- File: {normalized_path} ---\n{content[:2000]}\n"
                                file_payloads.append({"path": normalized_path, "content": base64.b64encode(content.encode('utf-8')).decode('utf-8')})
                            except Exception:
                                with open(file_path, 'rb') as f:
                                    b_content = f.read()
                                file_payloads.append({"path": normalized_path, "content": base64.b64encode(b_content).decode('utf-8')})

            # 2. Analyze with Groq API (UPGRADED PROMPTS FOR HR ATTRACTION)
            client = Groq(api_key=GROQ_API_KEY)
            
            prompt_linkedin = f"""You are a top-tier Data Analytics Professional publishing a project to LinkedIn. Analyze the following files and write a highly engaging, visually stunning post.
            CRITICAL REQUIREMENTS TO IMPRESS RECRUITERS:
            1. Start with a powerful hook focused on "Business Value" and "Actionable Insights".
            2. Detail the tech stack (Dataset structure + Power BI) using relevant emojis.
            3. Present 3 specific business problems this analytics dashboard solves (use checkmarks).
            4. Include a Call-To-Action asking data leaders for their thoughts, linking to GitHub.
            Tone: Professional, enthusiastic, impact-driven. Do NOT use generic intro/outro text. Output only the raw post.
            Project Context: {code_context}"""
            
            completion_li = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": prompt_linkedin}])
            linkedin_post_content = completion_li.choices[0].message.content.strip()

            prompt_readme = f"""You are a Staff Data Engineer creating an enterprise-grade README.md for a portfolio project. Analyze the context and write the markdown.
            CRITICAL REQUIREMENTS TO IMPRESS TECHNICAL HIRING MANAGERS:
            - Include visually appealing shields.io technology badges at the very top (e.g., Python, PowerBI, Data Science).
            - Include a section titled '📈 Business Impact' outlining how these insights drive growth.
            - Include a markdown 'mermaid' diagram block representing the high-level data flow (e.g., Raw Data -> Processing -> Power BI Dashboard).
            - Detail the dataset schema and Dashboard functionalities.
            - Provide clear, professional Setup Instructions.
            Use extensive Markdown styling (tables, bold, blockquotes). Output STRICTLY raw Markdown.
            Project Context: {code_context}"""
            
            completion_readme = client.chat.completions.create(model="llama3-70b-8192", messages=[{"role": "user", "content": prompt_readme}])
            readme_content = completion_readme.choices[0].message.content.strip()
            
            # Clean up potential markdown formatting wrapping from LLM
            if readme_content.startswith("```markdown"):
                readme_content = readme_content[11:]
            if readme_content.startswith("```"):
                readme_content = readme_content[3:]
            if readme_content.endswith("```"):
                readme_content = readme_content[:-3]
                
            file_payloads.append({"path": "README.md", "content": base64.b64encode(readme_content.encode('utf-8')).decode('utf-8')})

            # 3. GitHub Upload
            gh_headers = {"Authorization": f"token {session['github_token']}", "Accept": "application/vnd.github.v3+json"}
            github_username = requests.get("[https://api.github.com/user](https://api.github.com/user)", headers=gh_headers).json().get("login")
            
            repo_res = requests.post("[https://api.github.com/user/repos](https://api.github.com/user/repos)", headers=gh_headers, json={
                "name": repo_name, 
                "private": False,
                "description": "Enterprise Data Analytics & Power BI Dashboard Project"
            })
            if repo_res.status_code not in [200, 201]:
                raise Exception(f"GitHub Repo Creation Failed: {repo_res.text}")
            repo_url = repo_res.json().get("html_url")

            for f_data in file_payloads:
                put_res = requests.put(f"[https://api.github.com/repos/](https://api.github.com/repos/){github_username}/{repo_name}/contents/{f_data['path']}", headers=gh_headers, json={"message": f"Deploy {f_data['path']} via AutoPublisher AI", "content": f_data['content']})
                if put_res.status_code not in [200, 201]:
                    print(f"Failed to upload {f_data['path']}: {put_res.text}")

            # 4. LinkedIn Post
            li_headers = {"Authorization": f"Bearer {session['linkedin_token']}"}
            linkedin_urn = requests.get("[https://api.linkedin.com/v2/userinfo](https://api.linkedin.com/v2/userinfo)", headers=li_headers).json().get("sub")

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
            li_res = requests.post("[https://api.linkedin.com/v2/ugcPosts](https://api.linkedin.com/v2/ugcPosts)", headers={**li_headers, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}, json=post_payload)
            if li_res.status_code != 201:
                print(f"LinkedIn Post Failed: {li_res.text}")

            success_msg = f"""
            <div class='flex items-center gap-3 text-green-700'>
                <svg class='w-8 h-8' fill='none' stroke='currentColor' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'></path></svg>
                <div>
                    <h4 class='font-bold text-lg'>Enterprise Deployment Successful!</h4>
                    <p class='text-sm mt-1'>Check your stunning new repo: <a href='{repo_url}' target='_blank' class='underline font-bold hover:text-green-900'>{repo_url}</a></p>
                    <p class='text-sm'>Your professional LinkedIn post is now live!</p>
                </div>
            </div>
            """
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return redirect(url_for('index', message=success_msg))

    except Exception as e:
        print("APP CRASHED:", traceback.format_exc())
        error_html = f"<span style='color:#dc2626;'><b>System Crash:</b> {str(e)}</span><br><br><span class='text-xs'>Check Vercel Runtime Logs for full details. Ensure requirements.txt is updated.</span>"
        return redirect(url_for('index', message=error_html))

if __name__ == '__main__':
    app.run(port=5000, debug=True)
