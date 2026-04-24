import os
from flask import Flask, request
import boto3
from datetime import datetime

app = Flask(__name__)

# Инициализация клиентов AWS
# Добавляем 'rekognition' для цензуры
s3 = boto3.client('s3', 
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION')
)
rekognition = boto3.client('rekognition',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION')
)

@app.route('/')
def index():
    return '''
    <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #0078d4;">🛡️ Secure AI Gateway (Azure + AWS)</h1>
        <p>Все файлы проходят глубокую нейронную проверку на насилие, кровь и жесты.</p>
        <form action="/upload" method="post" enctype="multipart/form-data" style="background: #1e1e1e; padding: 30px; border-radius: 10px; display: inline-block; border: 1px solid #333;">
            <input type="file" name="file" required><br><br>
            <button type="submit" style="background: #d40000; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">Проверить и загрузить</button>
        </form>
    </body>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return "Ошибка: файл не выбран"
    
    bucket_name = "media-vault-ruslan-2026"
    file_bytes = file.read() # Считываем файл для анализа
    
    try:
        # --- ШАГ 1: НЕЙРОННАЯ ЦЕНЗУРА (AWS Rekognition) ---
        moderation_response = rekognition.detect_moderation_labels(
            Image={'Bytes': file_bytes},
            MinConfidence=10 # Максимальная чувствительность
        )
        
        labels = moderation_response.get('ModerationLabels', [])
        
        if labels:
            # Если найдены запрещенные элементы
            forbidden_stuff = ", ".join([l['Name'] for l in labels])
            return f'''
            <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #ff4444;">🚫 ДОСТУП ЗАБЛОКИРОВАН</h1>
                <p>Нейросеть обнаружила недопустимый контент: <b>{forbidden_stuff}</b></p>
                <p>Данный файл не будет сохранен в облаке.</p>
                <a href="/" style="color: #0078d4;">Попробовать другой файл</a>
            </body>
            '''

        # --- ШАГ 2: ЗАГРУЗКА (только если файл прошел проверку) ---
        file.seek(0) # Сбрасываем указатель файла после чтения
        s3.put_object(Bucket=bucket_name, Key=file.filename, Body=file_bytes)
        
        # --- ШАГ 3: ЛОГИРОВАНИЕ В DYNAMODB ---
        dynamo = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION'))
        table = dynamo.Table('CloudFiles')
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'CLEAN_AND_VERIFIED',
            'timestamp': datetime.now().isoformat(),
            'safety_score': '100%',
            'server': 'Azure-B1-Student'
        })
        
        return f"<h1>Успех!</h1><p>Файл {file.filename} прошел цензуру и сохранен.</p><a href='/'>Назад</a>"
        
    except Exception as e:
        return f"Ошибка безопасности: {str(e)}"

if __name__ == '__main__':
    app.run()