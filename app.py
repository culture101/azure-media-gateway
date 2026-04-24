import os
from flask import Flask, request
import boto3
from datetime import datetime

app = Flask(__name__)

# Настройки AWS берутся из твоих переменных среды в Azure
s3 = boto3.client('s3', 
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION')
)

@app.route('/')
def index():
    return '''
    <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>Azure-to-AWS Secure Gateway</h1>
        <form action="/upload" method="post" enctype="multipart/form-data" style="background: #1e1e1e; padding: 30px; border-radius: 10px; display: inline-block;">
            <input type="file" name="file" required><br><br>
            <button type="submit" style="background: #0078d4; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">Загрузить через Azure в AWS S3</button>
        </form>
    </body>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return "Ошибка: файл не выбран"
    
    # Твоя корзина из AWS S3
    bucket_name = "media-vault-ruslan-2026" 
    
    try:
        # 1. Загрузка файла в S3
        s3.upload_fileobj(file, bucket_name, file.filename)
        
        # 2. Логирование в DynamoDB (таблица CloudFiles из прошлой лабы)
        dynamo = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION'))
        table = dynamo.Table('CloudFiles')
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'verified_by_azure',
            'timestamp': datetime.now().isoformat(),
            'server_plan': 'B1_Student'
        })
        
        return f"<h1>Успех!</h1><p>Файл {file.filename} сохранен в AWS S3 и отмечен в DynamoDB.</p><a href='/'>Назад</a>"
    except Exception as e:
        return f"Ошибка при загрузке: {str(e)}"