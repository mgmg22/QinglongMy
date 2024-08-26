"""
cron: 00 35 23 * * 7  send_qq_email.py
new Env('qq邮件');
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

sender = os.getenv('EMAIL_ADDRESS')
receiver = os.getenv('EMAIL_ADDRESS')
password = os.getenv('EMAIL_PWD')
# 附件文件路径
attachment_path = 'xb.db'
smtp_server = 'smtp.qq.com'
smtp_port = 465

msg = MIMEMultipart()
msg['From'] = f' <{sender}>'
msg['To'] = f' <{receiver}>'
subject = 'xb.db附件'
msg['Subject'] = '邮件主题：带有xb.db附件的邮件。'

body = MIMEText('这是邮件正文内容。', 'plain', 'utf-8')
msg.attach(body)

with open(attachment_path, 'rb') as attachment_file:
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment_file.read())

encoders.encode_base64(part)
part.add_header('Content-Disposition', 'attachment', filename=attachment_path)
msg.attach(part)

if __name__ == "__main__":
    try:
        # 连接SMTP服务器
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, password)
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        print("邮件发送成功")

    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件", e)

    finally:
        server.quit()
