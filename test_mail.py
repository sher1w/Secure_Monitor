import smtplib, ssl, os

server = "smtp.gmail.com"
port   = 587
user   = os.environ["SMTP_USER"]
pwd    = os.environ["SMTP_PASS"]

print("logining in  as:", user)

context = ssl.create_default_context()
with smtplib.SMTP(server, port) as smtp:
    smtp.starttls(context=context)
    smtp.login(user, pwd)
    print("Success")
