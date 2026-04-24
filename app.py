import os
import io
import boto3
from flask import Flask, request
from datetime import datetime
from PIL import Image

app = Flask(__name__)

# Единый регион для всех сервисов
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
        <h1 style="color: #0078d4;">🛡️ Secure AI Gateway</h1>
        <p>Нейронная проверка файлов на безопасность.</p>
        <form action="/upload" method="post" enctype="multipart/form-data" style="background: #1e1e1e; padding: 30px; border-radius: 10px; display: inline-block; border: 1px solid #333;">
            <input type="file" name="file" required><br><br>
            <button type="submit" style="background: #d40000; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">Проверить и загрузить</button>
        </form>
    </body>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file: return "Файл не выбран"
    
    # ТВОИ НАЗВАНИЯ ИЗ AWS
    bucket_name = "ruslan-media-vault-central-2026"
    table_name = "VerifiedMedia"
    
    try:
        # Конвертация в JPEG для стабильной работы Rekognition
        in_memory_file = io.BytesIO(file.read())
        img = Image.open(in_memory_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        out_stream = io.BytesIO()
        img.save(out_stream, format='JPEG')
        final_bytes = out_stream.getvalue()

        # --- ШАГ 1: ПРОВЕРКА ИИ ---
        moderation = rekognition.detect_moderation_labels(
            Image={'Bytes': final_bytes},
            MinConfidence=20
        )
        
        labels = moderation.get('ModerationLabels', [])
        if labels:
            forbidden = ", ".join([l['Name'] for l in labels])
            return f"<h1>БЛОКИРОВКА</h1><p>Найдено: {forbidden}</p><a href='/'>Назад</a>"

        # --- ШАГ 2: ЗАГРУЗКА В S3 ---
        s3.put_object(
            Bucket=bucket_name, 
            Key=file.filename, 
            Body=final_bytes,
            ContentType='image/jpeg'
        )
        
        # --- ШАГ 3: ЗАПИСЬ В DYNAMODB ---
        dynamo = boto3.resource('dynamodb', region_name=REGION)
        table = dynamo.Table(table_name)
        table.put_item(Item={
            'file_id': file.filename,
            'status': 'CLEAN',
            'timestamp': datetime.now().isoformat(),
            'method': 'AI_Verified'
        })
        
        return "<h1>УСПЕХ!</h1><p>Файл прошел проверку и сохранен.</p><a href='/'>Назад</a>"
        
    except Exception as e:
        return f"Ошибка обработки: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)