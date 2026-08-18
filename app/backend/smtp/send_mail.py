import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mongo_table_connecters.mail_template import get_mail_template_by_name


def send_approve_mail(host = None, port = None, sender = None, password = None, receiver = None,team_name = None,full_name = None,employee_id=None,company_email=None,phone_number=None,system_url=None):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    mail_template = get_mail_template_by_name("send_approve")
    msg["Subject"] = str(mail_template['subject']).replace("{team_name}",team_name)
    html_body = str(mail_template['body']).replace("{team_name}",team_name).replace("{full_name}",full_name).replace("{employee_id}",employee_id).replace("{company_email}",company_email).replace("{phone_number}",phone_number).replace("{system_url}",system_url)
    
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(sender, password)
        server.send_message(msg)

def approved_mail(host = None, port = None, sender = None, password = None, receiver = None,bcc = None,team_name = None,full_name = None,system_url=None):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    mail_template = get_mail_template_by_name("approved")
    msg["Subject"] = str(mail_template['subject']).replace("{team_name}",team_name)
    html_body = str(mail_template['body']).replace("{team_name}",team_name).replace("{full_name}",full_name).replace("{system_url}",system_url)
    all_receivers = receiver.split(", ") + bcc
    
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(sender, password)
        server.send_message(msg,from_addr=sender,to_addrs=all_receivers)

def rejected_mail(host = None, port = None, sender = None, password = None, receiver = None,bcc = None,team_name = None,full_name = None,system_url=None):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    mail_template = get_mail_template_by_name("rejected")
    msg["Subject"] = str(mail_template['subject']).replace("{team_name}",team_name)
    html_body = str(mail_template['body']).replace("{team_name}",team_name).replace("{full_name}",full_name).replace("{system_url}",system_url)
    all_receivers = receiver.split(", ") + bcc
    
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(sender, password)
        server.send_message(msg,from_addr=sender,to_addrs=all_receivers)