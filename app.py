import os
from flask import Flask, request
import boto3
from datetime import datetime

app = Flask(__name__)

# Используем единый регион для всех сервисов
REGION = os.environ.get('AWS_REGION', 'eu-central-1')

# Инициализация клиентов AWS
s3 = boto3.client('s3', 
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=REGION
)

rekognition = boto3.client('rekognition',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=REGION
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
    
    # ТВОИ ОБНОВЛЕННЫЕ НАЗВАНИЯ
    bucket_name = "ruslan-secure-media-2026"
    table_name = "VerifiedMedia"
    
    try:
        # Читаем байты один раз в самом начале
        image_bytes = file.read()
        
        if not image_bytes:
            return "Ошибка: файл пуст"

        # --- ШАГ 1: НЕЙРОННАЯ ЦЕНЗУРА (AWS Rekognition) ---
        # Мы передаем image_bytes напрямую
        moderation_response = rekognition.detect_moderation_labels(
            Image={'Bytes': image_bytes},
            MinConfidence=20 # Оптимальная чувствительность
        )
        
        labels = moderation_response.get('ModerationLabels', [])
        
        if labels:
            forbidden_stuff = ", ".join([f"{l['Name']} ({round(l['Confidence'], 1)}%)" for l in labels])
            return f'''
            <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #ff4444;">🚫 ДОСТУП ЗАБЛОКИРОВАН</h1>
                <p>Нейросеть обнаружила недопустимый контент: <b>{forbidden_stuff}</b></p>
                <p>Данный файл был удален из памяти сервера и не попал в облако.</p>
                <a href="/" style="color: #0078d4; text-decoration: none;">← Вернуться назад</a>
            </body>
            '''

        # --- ШАГ 2: ЗАГРУЗКА В S3 (если файл чист) ---
        # Используем те же байты, что и для проверки
        s3.put_object(
            Bucket=bucket_name, 
            Key=file.filename, 
            Body=image_bytes,
            ContentType=file.content_type # Важно для корректного отображения в браузере
        )
        
        # --- ШАГ 3: ЛОГИРОВАНИЕ В DYNAMODB ---
        dynamo = boto3.resource('dynamodb', region_name=REGION)
        table = dynamo.Table(table_name)
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'CLEAN_AND_VERIFIED',
            'timestamp': datetime.now().isoformat(),
            'safety_score': '100%',
            'ai_provider': 'AWS Rekognition'
        })
        
        return f'''
        <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #28a745;">✅ УСПЕШНО</h1>
            <p>Файл <b>{file.filename}</b> успешно прошел проверку ИИ и сохранен в {bucket_name}.</p>
            <a href="/" style="color: #0078d4; text-decoration: none;">Загрузить еще один</a>
        </body>
        '''
        
    except Exception as e:
        # Выводим подробную ошибку для отладки
        return f'''
        <body style="background: #121212; color: white; font-family: sans-serif; padding: 50px;">
            <h2 style="color: #ffbb33;">Ошибка обработки</h2>
            <code style="background: #000; padding: 10px; display: block; color: #ff4444;">{str(e)}</code>
            <br><a href="/" style="color: #0078d4;">Назад</a>
        </body>
        '''

if __name__ == '__main__':
    # В Azure используется порт 8000 или 80, Flask по умолчанию берет 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)