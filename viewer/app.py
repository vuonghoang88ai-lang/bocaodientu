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

def init_settings_table():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                setting_key VARCHAR(255) PRIMARY KEY,
                setting_value VARCHAR(255)
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error creating user_settings table:", e)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM user_settings;")
        settings = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({row[0]: row[1] for row in settings})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def set_setting():
    data = request.json
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"success": False, "error": "Missing key"}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_settings (setting_key, setting_value) 
            VALUES (%s, %s) 
            ON CONFLICT (setting_key) 
            DO UPDATE SET setting_value = EXCLUDED.setting_value;
        """, (key, str(value).lower()))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT published_time, company_name, location, announcement_type FROM announcements WHERE length(company_name) > 5 GROUP BY published_time, company_name, location, announcement_type ORDER BY MAX(id) DESC LIMIT 500;")
        announcements = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        announcements = []
        print("Error connecting to DB:", e)
        
    settings = {}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM user_settings;")
        for row in cur.fetchall():
            settings[row[0]] = row[1]
        cur.close()
        conn.close()
    except Exception as e:
        print("Error getting settings:", e)
        
    return render_template('index.html', announcements=announcements, settings=settings)

@app.route('/api/download_pdf_auto/<ma_so_dn>', methods=['POST'])
def api_download_pdf_auto(ma_so_dn):
    if not download_pdf_auto:
        return jsonify({"success": False, "error": "Module pdf_downloader không tồn tại."}), 500
        
    data = request.json or {}
    announcement_type = data.get("announcement_type", "")
    published_time = data.get("published_time", "")
    save_to_drive = data.get("save_to_drive", False)
    
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    
    async def process_download():
        res = await download_pdf_auto(ma_so_dn, announcement_type, published_time, download_dir)
        if res.get("success"):
            if save_to_drive:
                try:
                    from drive_helper import upload_to_drive_async
                    folder_id = "115kCxRtcX2S0yb9L2FVDTbyaDF11HQzn"
                    drive_link = await upload_to_drive_async(res["file_path"], f"{ma_so_dn}.pdf", folder_id)
                    res["download_url"] = drive_link
                    res["is_drive_link"] = True
                    
                    # Update DB
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE announcements SET pdf_path = %s WHERE company_name LIKE %s AND announcement_type = %s", (drive_link, f"%{ma_so_dn}%", announcement_type))
                        conn.commit()
                        cur.close()
                        conn.close()
                    except Exception as db_e:
                        print("Error updating DB:", db_e)
                        
                except Exception as up_e:
                    res["success"] = False
                    res["error"] = "Lỗi khi upload lên Google Drive: " + str(up_e)
            else:
                rel_path = res.get("rel_path")
                if not rel_path:
                    # Fallback if rel_path is missing
                    rel_path = os.path.basename(res["file_path"])
                res["download_url"] = f"/download/{rel_path}"
                res["is_drive_link"] = False
        return res

    try:
        result = asyncio.run(process_download())
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
            rel_path = result.get("rel_path", os.path.basename(result.get("file_path", "")))
            result["download_url"] = f"/download/{rel_path}"
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    return send_from_directory(downloads_dir, filename, as_attachment=True)

if __name__ == '__main__':
    # Initialize settings table
    init_settings_table()
    app.run(host='0.0.0.0', port=3000)
