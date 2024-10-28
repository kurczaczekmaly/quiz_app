from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
import qrcode
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'tajny_klucz')
socketio = SocketIO(app)

# Przechowywanie sesji quizów
quizzes = {}

# Ścieżka do folderu z kodami QR
QR_FOLDER = 'static/qr_codes'
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

@app.route('/')
def index():
    return redirect(url_for('host'))

@app.route('/host')
def host():
    # Tworzenie unikalnego ID sesji
    session_id = str(uuid.uuid4())
    quizzes[session_id] = {
        'participants': {},
        'questions': [],
        'current_question': None
    }
    
    # Generowanie URL do dołączenia
    join_url = url_for('participant', session_id=session_id, _external=True)
    
    # Generowanie kodu QR
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5
    )
    qr.add_data(join_url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    qr_path = os.path.join(QR_FOLDER, f'{session_id}.png')
    img.save(qr_path)
    
    return render_template('host.html', session_id=session_id, qr_url=url_for('static', filename=f'qr_codes/{session_id}.png'))

@app.route('/participant/<session_id>')
def participant(session_id):
    if session_id not in quizzes:
        return "Sesja nie istnieje!", 404
    return render_template('participant.html', session_id=session_id)

@socketio.on('join')
def handle_join(data):
    session_id = data['session_id']
    name = data['name']
    if session_id in quizzes:
        room = session_id
        join_room(room)
        participant_id = str(uuid.uuid4())
        quizzes[session_id]['participants'][participant_id] = {
            'name': name,
            'score': 0
        }
        emit('join_accepted', {'participant_id': participant_id}, room=request.sid)
        emit('update_participants', quizzes[session_id]['participants'], room=room)
    else:
        emit('error', {'message': 'Sesja nie istnieje.'})

@socketio.on('start_quiz')
def handle_start_quiz(data):
    session_id = data['session_id']
    questions = data['questions']  # Lista pytań
    if session_id in quizzes:
        quizzes[session_id]['questions'] = questions
        emit('quiz_started', {}, room=session_id)

@socketio.on('send_question')
def handle_send_question(data):
    session_id = data['session_id']
    question = data['question']
    options = data['options']
    quizzes[session_id]['current_question'] = {
        'question': question,
        'options': options,
        'answers': {}
    }
    emit('new_question', quizzes[session_id]['current_question'], room=session_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    session_id = data['session_id']
    participant_id = data['participant_id']
    answer = data['answer']
    current_question = quizzes[session_id].get('current_question', None)
    if current_question:
        current_question['answers'][participant_id] = answer
        # Możesz tutaj dodać logikę oceny odpowiedzi
        # Przykład: zakładamy, że poprawna odpowiedź to 'A'
        if answer == 'A':
            quizzes[session_id]['participants'][participant_id]['score'] += 1
        emit('answer_received', {'participant_id': participant_id, 'answer': answer}, room=session_id)

@socketio.on('get_results')
def handle_get_results(data):
    session_id = data['session_id']
    if session_id in quizzes:
        emit('results', quizzes[session_id]['participants'], room=session_id)

@socketio.on('disconnect')
def handle_disconnect():
    # Obsługa rozłączenia użytkownika
    pass

if __name__ == '__main__':
    socketio.run(app, debug=True)
