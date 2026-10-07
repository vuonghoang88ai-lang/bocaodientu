from flask import Flask, render_template, jsonify, request, send_from_directory
import psycopg2
import os
import sys
import asyncio

try:
    from pdf_downloader import download_pdf_auto
except ImportError as e:
    print("Import error:", e)
    download_pdf_auto = None

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'db'),
        database=os.getenv('DB_NAME', 'dkkd_data'),
        user=os.getenv('DB_USER', 'crawler_user'),
        password=os.getenv('DB_PASSWORD', 'your_password'),
        port=os.getenv('DB_PORT', '5432')
    )
    return conn

@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT published_time, company_name, location, announcement_type FROM announcements WHERE length(company_name) > 5 ORDER BY id DESC LIMIT 100;")
        announcements = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        announcements = []
        print("Error connecting to DB:", e)
        
    return render_template('index.html', announcements=announcements)

@app.route('/api/download_pdf_auto/<ma_so_dn>', methods=['POST'])
def api_download_pdf_auto(ma_so_dn):
    if not download_pdf_auto:
        return jsonify({"success": False, "error": "Module pdf_downloader không tồn tại."}), 500
        
    data = request.json or {}
    announcement_type = data.get("announcement_type", "")
    
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    
    try:
        result = asyncio.run(download_pdf_auto(ma_so_dn, announcement_type, download_dir))
        if result.get("success"):
            result["download_url"] = f"/download/{ma_so_dn}.pdf"
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/download_pdf_manual/<ma_so_dn>', methods=['POST'])
def api_download_pdf_manual(ma_so_dn):
    if not download_pdf_with_token:
        return jsonify({"success": False, "error": "Module pdf_downloader không tồn tại."}), 500
    
    data = request.json
    token = data.get("g-recaptcha-response")
    if not token:
        return jsonify({"success": False, "error": "Không có token Captcha"}), 400

    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    
    try:
        result = asyncio.run(download_pdf_with_token(ma_so_dn, token, download_dir))
        if result.get("success"):
            result["download_url"] = f"/download/{ma_so_dn}.pdf"
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    return send_from_directory(downloads_dir, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
