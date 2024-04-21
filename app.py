from flask import Flask, request, send_file, render_template
import os
import re
import emoji
import google.generativeai as genai
from PIL import Image
from io import BytesIO
import requests
import pandas as pd
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("API_KEY")

API_KEY="AIzaSyBDh55zKHPoQ8jddRt0OzzOv8slXtOK0Mk"
genai.configure(api_key=API_KEY, transport="rest")
app = Flask(__name__)
CORS(app)

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/upload-excel', methods=['POST'])
def upload_excel():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    try:
        stream = BytesIO()
        file.save(stream)
        stream.seek(0)
        df = pd.read_excel(stream)

        if df is not None and '代理链接 2' in df.columns and 'SKU' in df.columns:
            new_df = pd.DataFrame(columns=['SKU', 'GPT-Title', '代理链接 2'])
            for idx, row in df.iterrows():
                compressed_image = compress_image(row['代理链接 2'])
                clothing_title = generate_clothing_title(compressed_image)
                new_df.loc[idx] = [row['SKU'], clothing_title, row['代理链接 2']]

            output = BytesIO()
            new_df.to_excel(output, index=False)
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name='processed.xlsx',  # Use this if your Flask version is older than 2.0
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        else:
            return "Required columns are missing in the Excel file.", 400
    except Exception as e:
        print(str(e))
        return str(e), 500

def format_title(title):
    if title is None:
        return None
    # 将emoji替换为对应的英文词语
    title = emoji.demojize(title, delimiters=(" ", " "))
    # 去除首尾空格
    title = title.strip()
    # 替换 -, | 和多个空格为一个空格
    title = re.sub(r'[-|,\r\n]]+', ' ', title)
    # 将多个连续空格替换为一个空格
    title = re.sub(r'\s+', ' ', title)
    return title


def compress_image(image_url):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img = img.convert('RGB')
            img = img.resize((img.width // 2, img.height // 2))
            output_buffer = BytesIO()
            img.save(output_buffer, format="JPEG", quality=85)
            compressed_data = output_buffer.getvalue()
            print(f"successful Compressing {image_url}")
            return Image.open(BytesIO(compressed_data))
        else:
            print("Failed to download image:", response.status_code)
            return None
    except Exception as e:
        print("Error:", e)
        return None

def generate_clothing_title(image):
    if image is None:
        return None

    model = genai.GenerativeModel("gemini-pro-vision")
    fb = "Descriptive words should be placed before words describing clothing types (e.g., Blouse, Shirts, T-shirts, Tops) to form a complete phrase. For example, 'V-Neck', 'Button Down 3/4 Sleeve' should be combined with 'Blouse', 'Shirts', 'T-shirts', 'Tops' to create a complete and descriptive phrase, rather than separated. This helps to clearly describe the style and features of the clothing."
    kn = "The structure of a clothing title typically includes the following aspects: Gender: Indicates the gender the clothing is designed for. Core Descriptor: Represents the main type or feature of the clothing, such as Tank Top or T-Shirt. Print Style: Describes the print or pattern on the clothing. Fit: Describes the fit of the clothing, such as Slim Fit or Oversize. Cut: Describes the design or intended use of the clothing, such as Bodybuilding for gym wear. Sleeve Type: Describes the type of sleeves on the clothing, such as Sleeveless. Neckline: Describes the style of the neckline, such as Scoop Neck. Additional Features: Describes other features of the clothing, such as stretchiness, lightweight, or breathability."
    wtd = "Based on the details shown in the clothing picture, please summarize and create an e-commerce clothing title in English within 200 characters. Remove the brand name, and use only spaces as division symbols."
    question = kn + " " + wtd + " " + fb

    attempt_count = 0
    max_attempts = 3
    while attempt_count < max_attempts:
        try:
            response = model.generate_content([question, image], stream=False)
            response.resolve()
            print(response.text)
            return format_title(response.text)
        except Exception as e:
            attempt_count += 1
            print(f"Error generating title: {e}. Attempting again... ({attempt_count}/{max_attempts})")
    print("Failed to generate title after maximum attempts.")
    return None

if __name__ == '__main__':
    app.run(debug=True)
