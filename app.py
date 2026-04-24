import os
import io
from flask import Flask, request
import boto3
from datetime import datetime
from PIL import Image # Добавили для исправления форматов

app = Flask(__name__)

# Регион из настроек Azure
REGION = os.environ.get('AWS_REGION', 'eu-central-1')

# Клиенты AWS
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
        <p>Нейронная проверка на насилие, кровь и нежелательный контент.</p>
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
    
    bucket_name = "ruslan-secure-media-2026"
    table_name = "VerifiedMedia"
    
    try:
        # --- ШАГ 0: ПРИНУДИТЕЛЬНАЯ КОНВЕРТАЦИЯ В JPEG ---
        # Это лечит ошибку InvalidImageFormatException
        img = Image.open(file)
        if img.mode in ("RGBA", "P"): # Убираем прозрачность
            img = img.convert("RGB")
            
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        final_bytes = img_byte_arr.getvalue()

        # --- ШАГ 1: НЕЙРОННАЯ ЦЕНЗУРА ---
        moderation_response = rekognition.detect_moderation_labels(
            Image={'Bytes': final_bytes},
            MinConfidence=15
        )
        
        labels = moderation_response.get('ModerationLabels', [])
        
        if labels:
            forbidden_stuff = ", ".join([f"{l['Name']}" for l in labels])
            return f'''
            <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #ff4444;">🚫 ДОСТУП ЗАБЛОКИРОВАН</h1>
                <p>Нейросеть обнаружила: <b>{forbidden_stuff}</b></p>
                <a href="/" style="color: #0078d4; text-decoration: none;">Назад</a>
            </body>
            '''

        # --- ШАГ 2: ЗАГРУЗКА В S3 ---
        s3.put_object(
            Bucket=bucket_name, 
            Key=file.filename, 
            Body=final_bytes,
            ContentType='image/jpeg'
        )
        
        # --- ШАГ 3: DYNAMODB ---
        dynamo = boto3.resource('dynamodb', region_name=REGION)
        table = dynamo.Table(table_name)
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'CLEAN',
            'timestamp': datetime.now().isoformat()
        })
        
        return f'''
        <body style="background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #28a745;">✅ УСПЕШНО</h1>
            <p>Файл прошел проверку и сохранен.</p>
            <a href="/" style="color: #0078d4; text-decoration: none;">Загрузить еще</a>
        </body>
        '''
        
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)