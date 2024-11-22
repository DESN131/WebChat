from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'  # SQLite database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app)
db = SQLAlchemy(app)

# User Table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Message Table
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database
with app.app_context():
    db.create_all()

# Store session ID and username
usernames = {}  # session ID -> username

# Route: index page
@app.route('/')
def index():
    return render_template('login.html')

# Route: register page
@app.route('/register')
def register_page():
    return render_template('register.html')

# Route: chat page
@app.route('/chat')
def chat_page():
    return render_template('chat.html')

# Register API
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'}), 400

    hashed_password = generate_password_hash(password)  # 加密密码
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'message': '注册成功'})

# Login API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        return jsonify({'success': True, 'message': '登录成功'})
    return jsonify({'success': False, 'message': '用户名或密码错误'}), 400

# WebSocket Set Username
@socketio.on('set_username')
def set_username(data):
    user_id = request.sid
    username = data.get('username', '').strip()
    if username:
        usernames[user_id] = username
        print(f"{username} 已连接")
        emit('username_set', username)
    else:
        emit('username_error', '用户名不能为空！')

# WebSocket Disconnect
@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid
    username = usernames.pop(user_id, 'Unknown')
    print(f"{username} 已断开连接")

# WebSocket Message
@socketio.on('message')
def handle_message(data):
    user_id = request.sid
    username = usernames.get(user_id, 'Unknown')
    message = data.get('message', '').strip()

    if message:
        # Save message to database
        new_message = Message(username=username, message=message)
        db.session.add(new_message)
        db.session.commit()

        # Broadcast message to all clients
        timestamp = new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        send({'username': username, 'message': message, 'timestamp': timestamp}, broadcast=True)

# WebSocket Fetch History
@socketio.on('fetch_history')
def fetch_history():
    messages = Message.query.order_by(Message.timestamp).all()
    history = [
        {
            'username': msg.username,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for msg in messages
    ]
    emit('chat_history', history)

# Run server
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
