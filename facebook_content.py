import re
import requests
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import schedule
import time

# Cấu hình MySQL
MYSQL_CONFIG = {
    "host": "52.184.83.97",
    "user": "nhoma",
    "password": "123",
    "database": "managerwarehouse"
}

# Cấu hình Facebook API
APP_ID = '2079935909189873'
APP_SECRET = '05eb99381e53bbc658241aa8e1d6ab9e'
ACCESS_TOKEN = 'EAAdjsNEF2PEBOyaW8wM4gOJXAedYHoZCoZBkbjbGqkJshMcNTACKGwFZC2BpEogHVa7MSk0i3mjpCoV9YX1ZCZAQlPzb8Whkg5MKYZAlXOHOTnqybrgRYOrlCEfReHQgs9dv1IOxwkfHZAhW5oQisgZCelWCHNyaQhXcZBZCXP1ieUR9ZAxEyL9EFVbt5f0o3Fbjtl8mRaWqoGL'
GROUP_ID = '549460434918855'
FB_EXCHANGE_TOKEN_URL = f"https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={ACCESS_TOKEN}"

# Cấu hình Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "winzero26@gmail.com"
EMAIL_PASSWORD = "xtbfixuiszbrljxu"
EMAIL_RECEIVERS = ["sharketernaldarkness@gmail.com", "chang.shuwei.job@gmail.com"]

# URL API Facebook
url = f"https://graph.facebook.com/v22.0/{GROUP_ID}/feed"
params = {
    'access_token': ACCESS_TOKEN,
    'limit': 10
}

keywords = ["新書上架", "享讀時光", "新書上架"]

# Kết nối MySQL
conn = mysql.connector.connect(**MYSQL_CONFIG)
cursor = conn.cursor()

def save_keyword(keyword):
    cursor.execute('SELECT COUNT(*) FROM keywords WHERE keyword = %s', (keyword,))
    exists_keyword = cursor.fetchone()[0]

    if exists_keyword == 0:
        cursor.execute('INSERT INTO keywords (keyword) VALUES (%s)', (keyword,))
        print(f"Keyword saved: {keyword}")
    else:
        print(f"Keyword already exists: {keyword}")

for keyword in keywords:
    save_keyword(keyword)
conn.commit()

def get_keywords():
    #Lấy danh sách từ khóa từ MySQL
    cursor.execute("SELECT keyword FROM keywords")
    return [row[0] for row in cursor.fetchall()]

def check_keywords(content, keywords):
    #Kiểm tra xem bài đăng có chứa từ khóa không
    if content:
        content_lower = content.lower()
        keywords_lower = [kw.lower() for kw in keywords]

        # 🔹 Kiểm tra từ khóa trong nội dung bài viết
        for keyword in keywords_lower:
            #pattern = r'\b' + re.escape(keyword) + r'\b'  # dùng cho tiếng việt
            pattern = re.escape(keyword)  # dùng cho nhiều ngôn ngữ
            if re.search(pattern, content_lower):
                return keyword

        # 🔹 Kiểm tra từ khóa trong hashtag
        hashtags = re.findall(r'#([^\s#]+)', content)  # Tìm hashtag chính xác hơn
        hashtags_lower = [tag.lower() for tag in hashtags]

        for keyword in keywords_lower:
            if keyword in hashtags_lower:
                return keyword

    return None
    

def save_post(post_id, content, created_time):
    #Lưu bài đăng vào bảng posts (nếu chưa tồn tại)
    cursor.execute("SELECT post_id FROM posts WHERE post_id = %s", (post_id,))
    if cursor.fetchone() is None:
        sql = "INSERT INTO posts (post_id, content, created_time) VALUES (%s, %s, %s)"
        cursor.execute(sql, (post_id, content, datetime.now()))
        conn.commit()
        print(f" Save post {post_id} to posts table")
    else:
        print(f" Post {post_id} already exists, ignore")

def save_matched_post(post_id, content, matched_keyword):
    #Lưu bài viết chứa từ khóa vào matched_posts
    cursor.execute("SELECT post_id FROM matched_posts WHERE post_id = %s", (post_id,))
    if cursor.fetchone() is None:
        sql = "INSERT INTO matched_posts (post_id, content, matched_keyword, sent_email) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (post_id, content, matched_keyword, False))
        conn.commit()
        print(f"The post {post_id} containing the keyword '{matched_keyword}' has been saved")

def send_email(post_id, content, matched_keyword):
    # Kiểm tra nếu email đã được gửi
    cursor.execute("SELECT sent_email FROM matched_posts WHERE post_id = %s", (post_id,))
    result = cursor.fetchone()
    if result and result[0]:  # Nếu `sent_email` là True thì không gửi lại
        print(f"Email has been sent for the post {post_id}, skip.")
        return
    #Gửi email thông báo#
    subject = f"📢 New article with keyword: {matched_keyword}"
    body = f"📌 ID: {post_id}\n📝 Content: \n{content}\n🔗 Link: https://www.facebook.com/{post_id}"
    
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = ", ".join(EMAIL_RECEIVERS)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS, msg.as_string())
        server.quit()
        print(f"Email notification sent about post {post_id}")
        
        # Cập nhật trạng thái gửi email trong DB
        cursor.execute("UPDATE matched_posts SET sent_email = TRUE WHERE post_id = %s", (post_id,))
        conn.commit()
    except Exception as e:
        print(f"Email sending error: {e}")

def get_facebook_posts():
    #Lấy bài đăng từ Facebook và kiểm tra từ khóa
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        posts = data.get('data', [])
        keywords = get_keywords()
        
        for post in posts:
            post_id = post.get('id', 'N/A')
            content = post.get('message')
            created_time = post.get('created_time', 'N/A')

            # print(f"📌 ID: {post_id}")
            # print(f"🕒 Time: {created_time}")
            # print(f"📜 Content: {content}\n{'-'*40}")

            # Lưu bài đăng vào bảng posts
            save_post(post_id, content, created_time)

            # Kiểm tra từ khóa
            matched_keyword = check_keywords(content, keywords)
            if matched_keyword:
                save_matched_post(post_id, content, matched_keyword)
                send_email(post_id, content, matched_keyword)
    else:
        print("Error while retrieving data:", response.status_code, response.text)

# Gọi hàm lấy bài đăng
get_facebook_posts()

def job():
    print("🔄 Running new post check...")
    get_facebook_posts()

# Lên lịch chạy mỗi 1 giờ
schedule.every(1).minutes.do(job)

print("✅ Facebook monitoring system is running. Every 1 hour will check for new posts...")
while True:
    schedule.run_pending()
    time.sleep(60)  # Kiểm tra mỗi phút để xem có lịch nào cần chạy không



