from flask import Flask, request, render_template, redirect, url_for
import pandas as pd
import json
import os
import speech_recognition as sr
from pydub import AudioSegment

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'txt', 'wav'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_customer_requirements(dialogue):
    requirements = {
        "Car_Type": None,
        "Fuel_Type": None,
        "Color": None,
        "Distance_Travelled": None,
        "Make_Year": None,
        "Transmission_Type": None
    }

    carmodel = ["SUV", "Land Cruizer", "Toyota", "Volkswagen", "Hatchback", "Sedan", "Limo", "Renault", "Honda", "Kia", "Porsche", "Kisan", "Ford", "Tesla", "Lamborghini", "Indica", "Mahindra", "Tata", "Rover", "Jaguar", "Xylo"]
    year = [str(i) for i in range(1995, 2024)]
    colors = ["red", "blue", "yellow", "black", "white", "silver", "brown", "lilac", "maroon", "orange", "green", "gold", "gray"]
    ttype = ["Automatic", "automatic", "manual"]

    for i in carmodel:
        if i in dialogue:
            requirements["Car_Type"] = i
    for i in colors:
        if i in dialogue:
            requirements["Color"] = i
    for i in year:
        if i in dialogue:
            requirements["Make_Year"] = i
    if "automatic" in dialogue or "Automatic" in dialogue:
        requirements["Transmission_Type"] = "Automatic"

    return requirements

def process_csv(file_path):
    df = pd.read_csv(file_path)
    extracted_data = {}
    for transcript_id, group in df.groupby('Transcript_ID'):
        extracted_data[transcript_id] = {
            "Customer_Requirements": None,
            "Company_Policies": None,
            "Customer_Objections": None
        }

        for row in group.itertuples():
            if row.Speaker == 'Customer':
                if not extracted_data[transcript_id]["Customer_Requirements"]:
                    extracted_data[transcript_id]["Customer_Requirements"] = extract_customer_requirements(row.Dialogue)
                if "refurbishment quality" in row.Dialogue:
                    extracted_data[transcript_id]["Customer_Objections"] = "Refurbishment Quality"
                if "price" in row.Dialogue:
                    extracted_data[transcript_id]["Customer_Objections"] = "Price Issues"
            elif row.Speaker == 'Salesperson' and "5-Day Money Back Guarantee" in row.Dialogue:
                extracted_data[transcript_id]["Company_Policies"] = "5-Day Money Back Guarantee"

    return extracted_data

def parse_txt_file(file_path):
    transcript_ids = []
    speakers = []
    dialogues = []

    with open(file_path, 'r') as file:
        lines = file.readlines()
        for i in range(0, len(lines), 4):
            transcript_id = lines[i].split(': ')[1].strip()
            speaker = lines[i + 1].split(': ')[1].strip()
            dialogue = lines[i + 2].split(': ')[1].strip()

            transcript_ids.append(transcript_id)
            speakers.append(speaker)
            dialogues.append(dialogue)

    data = {
        'Transcript_ID': transcript_ids,
        'Speaker': speakers,
        'Dialogue': dialogues
    }

    return pd.DataFrame(data)

def convert_audio_to_text(audio_file_path, output_text_file):
    recognizer = sr.Recognizer()
    
    if not audio_file_path.lower().endswith('.wav'):
        audio = AudioSegment.from_file(audio_file_path)
        audio.export('temp.wav', format='wav')
        audio_file_path = 'temp.wav'
    
    with sr.AudioFile(audio_file_path) as source:
        audio_data = recognizer.record(source)
        
        try:
            text = recognizer.recognize_google(audio_data)
            with open(output_text_file, "w") as text_file:
                text_file.write(text)
        
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        if file.filename.endswith('.csv'):
            extracted_data = process_csv(file_path)
            json_output = json.dumps(extracted_data, indent=4)
            return render_template('display.html', is_json=True, json_data=json_output)

        elif file.filename.endswith('.txt'):
            df = parse_txt_file(file_path)
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'converted_from_txt.csv')
            df.to_csv(csv_path, index=False)
            extracted_data = process_csv(csv_path)
            json_output = json.dumps(extracted_data, indent=4)
            return render_template('display.html', is_json=True, json_data=json_output)

        elif file.filename.endswith('.wav'):
            text_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'transcription.txt')
            convert_audio_to_text(file_path, text_file_path)
            df = parse_txt_file(text_file_path)
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], 'converted_from_audio.csv')
            df.to_csv(csv_path, index=False)
            extracted_data = process_csv(csv_path)
            json_output = json.dumps(extracted_data, indent=4)
            return render_template('display.html', is_json=True, json_data=json_output)

    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
