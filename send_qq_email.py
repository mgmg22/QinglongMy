"""
cron: 00 35 23 * * 7  send_qq_email.py
new Env('qq邮件');
"""
import os
import markdown
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

sender = os.getenv('EMAIL_ADDRESS')
password = os.getenv('EMAIL_PWD')
receiver = sender
# 附件文件路径
attachment_path = 'xb.db'
smtp_server = 'smtp.qq.com'
smtp_port = 465


def generate_html_body():
    md_file_path = 'log_stock.md'
    with open(md_file_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()
    html_table = markdown.markdown(markdown_content, extensions=['tables'])
    return MIMEText(html_table, 'html', 'utf-8')


def generate_attachment():
    with open(attachment_path, 'rb') as attachment_file:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment_file.read())

    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=attachment_path)
    return part


def delete_attachment_file():
    if os.path.exists(attachment_path):
        try:
            os.remove(attachment_path)
            os.remove('wb.db')
            print(f"{attachment_path} 已被删除。")
        except OSError as e:
            print(f"删除{attachment_path} 出错: {e}")


msg = MIMEMultipart()
msg['From'] = f' <{sender}>'
msg['To'] = f' <{receiver}>'
msg['Subject'] = f'本周收盘行情及{attachment_path}附件。'

msg.attach(generate_html_body())
msg.attach(generate_attachment())

if __name__ == "__main__":
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, password)
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        print("邮件发送成功")
        delete_attachment_file()
    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件", e)
    finally:
        server.quit()
