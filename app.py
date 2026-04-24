import os
import io
from flask import Flask, request
import boto3
from datetime import datetime
from PIL import Image

app = Flask(__name__)

REGION = os.environ.get('AWS_REGION', 'eu-central-1')

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
        <h1 style="color: #0078d4;">🛡️ Secure AI Gateway</h1>
        <form action="/upload" method="post" enctype="multipart/form-data" style="background: #1e1e1e; padding: 30px; border-radius: 10px; display: inline-block; border: 1px solid #333;">
            <input type="file" name="file" required><br><br>
            <button type="submit" style="background: #d40000; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">Проверить и загрузить</button>
        </form>
    </body>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return "Файл не выбран"
    
    bucket_name = "ruslan-secure-media-2026"
    table_name = "VerifiedMedia"
    
    try:
        # --- ГАРАНТИРОВАННАЯ ОЧИСТКА ФОРМАТА ---
        # Читаем файл в память
        in_memory_file = io.BytesIO(file.read())
        img = Image.open(in_memory_file)
        
        # Конвертируем в RGB (убирает проблемы с прозрачностью PNG/WebP)
        img = img.convert('RGB')
        
        # Сохраняем в новый буфер как JPEG
        out_stream = io.BytesIO()
        img.save(out_stream, format='JPEG', quality=90)
        final_bytes = out_stream.getvalue()

        # --- ШАГ 1: ЦЕНЗУРА ---
        moderation = rekognition.detect_moderation_labels(
            Image={'Bytes': final_bytes},
            MinConfidence=20
        )
        
        labels = moderation.get('ModerationLabels', [])
        if labels:
            return f"<h1>БЛОКИРОВКА</h1><p>Найдено: {labels[0]['Name']}</p><a href='/'>Назад</a>"

        # --- ШАГ 2: ЗАГРУЗКА ---
        s3.put_object(
            Bucket=bucket_name, 
            Key=file.filename, 
            Body=final_bytes,
            ContentType='image/jpeg'
        )
        
        # --- ШАГ 3: ЛОГИ ---
        dynamo = boto3.resource('dynamodb', region_name=REGION)
        table = dynamo.Table(table_name)
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'CLEAN',
            'timestamp': datetime.now().isoformat()
        })
        
        return "<h1>УСПЕХ!</h1><p>Файл проверен и сохранен.</p><a href='/'>Назад</a>"
        
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)