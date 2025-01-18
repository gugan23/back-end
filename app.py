from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from pymongo import MongoClient
from bson import ObjectId
from datetime import timedelta, datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

load_dotenv()
app = Flask(__name__, static_folder='template-management/build')
CORS(app)

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
jwt = JWTManager(app)

# MongoDB Atlas Connection
MONGO_URI = os.getenv('MONGO_URI')
try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
    db = client['template_management']
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

# Root route
@app.route('/')
def home():
    return jsonify({'message': 'Welcome to Template Management API'}), 200

# Error handler for ObjectId conversion
@app.errorhandler(Exception)
def handle_invalid_usage(error):
    if "Invalid ObjectId" in str(error):
        return jsonify({"message": "Invalid template ID format"}), 400
    return jsonify({"message": str(error)}), 500

# User Registration
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400

        required_fields = ['first_name', 'last_name', 'email', 'password']

        # Validate required fields
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        # Check if email already exists
        if db.users.find_one({'email': data['email']}):
            return jsonify({'message': 'Email already registered'}), 400

        user = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'email': data['email'],
            'password': generate_password_hash(data['password']),
            'created_at': datetime.utcnow()
        }

        db.users.insert_one(user)
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# User Login
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400

        # Validate required fields
        if not all(field in data for field in ['email', 'password']):
            return jsonify({'message': 'Missing email or password'}), 400

        user = db.users.find_one({'email': data['email']})

        if user and check_password_hash(user['password'], data['password']):
            access_token = create_access_token(identity=str(user['_id']))
            return jsonify({
                'message': 'Login successful',
                'access_token': access_token
            }), 200

        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Template CRUD Operations
@app.route('/template', methods=['POST'])
@jwt_required()
def create_template():
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400

        # Validate required fields
        required_fields = ['template_name', 'subject', 'body']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        template = {
            'user_id': current_user,
            'template_name': data['template_name'],
            'subject': data['subject'],
            'body': data['body'],
            'created_at': datetime.utcnow()
        }

        result = db.templates.insert_one(template)
        return jsonify({
            'message': 'Template created',
            'id': str(result.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/template', methods=['GET'])
@jwt_required()
def get_all_templates():
    try:
        current_user = get_jwt_identity()
        templates = list(db.templates.find({'user_id': current_user}))

        # Convert ObjectId to string for JSON serialization
        for template in templates:
            template['_id'] = str(template['_id'])
            # Convert datetime objects to string
            if 'created_at' in template:
                template['created_at'] = template['created_at'].isoformat()
            if 'updated_at' in template:
                template['updated_at'] = template['updated_at'].isoformat()

        return jsonify(templates), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/template/<template_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def template_operations(template_id):
    try:
        current_user = get_jwt_identity()

        # Validate template_id format
        try:
            template_obj_id = ObjectId(template_id)
        except:
            return jsonify({'message': 'Invalid template ID format'}), 400

        if request.method == 'GET':
            template = db.templates.find_one({
                '_id': template_obj_id,
                'user_id': current_user
            })

            if not template:
                return jsonify({'message': 'Template not found'}), 404

            template['_id'] = str(template['_id'])
            # Convert datetime objects to string
            if 'created_at' in template:
                template['created_at'] = template['created_at'].isoformat()
            if 'updated_at' in template:
                template['updated_at'] = template['updated_at'].isoformat()

            return jsonify(template), 200

        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'message': 'No input data provided'}), 400

            # Validate required fields
            required_fields = ['template_name', 'subject', 'body']
            if not all(field in data for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            result = db.templates.update_one(
                {'_id': template_obj_id, 'user_id': current_user},
                {'$set': {
                    'template_name': data['template_name'],
                    'subject': data['subject'],
                    'body': data['body'],
                    'updated_at': datetime.utcnow()
                }}
            )

            if result.modified_count == 0:
                return jsonify({'message': 'Template not found'}), 404

            return jsonify({'message': 'Template updated successfully'}), 200

        elif request.method == 'DELETE':
            result = db.templates.delete_one({
                '_id': template_obj_id,
                'user_id': current_user
            })

            if result.deleted_count == 0:
                return jsonify({'message': 'Template not found'}), 404

            return jsonify({'message': 'Template deleted successfully'}), 200

    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Task CRUD Operations
@app.route('/task', methods=['POST'])
@jwt_required()
def create_task():
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400

        # Validate required fields
        required_fields = ['assigned_user', 'task_date', 'task_time', 'task_msg']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        assigned_user = db.users.find_one({'_id': ObjectId(data['assigned_user'])})
        if not assigned_user:
            return jsonify({'message': 'Assigned user not found'}), 404

        task = {
            'assigned_by': current_user,
            'assigned_user': data['assigned_user'],
            'task_date': data['task_date'],
            'task_time': data['task_time'],
            'task_msg': data['task_msg'],
            'is_completed': 0,
            'created_at': datetime.utcnow()
        }

        result = db.tasks.insert_one(task)
        return jsonify({
            'message': 'Task created',
            'id': str(result.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/task', methods=['GET'])
@jwt_required()
def get_tasks():
    try:
        current_user = get_jwt_identity()
        tasks = list(db.tasks.find({'assigned_user': current_user}))

        # Convert ObjectId to string for JSON serialization
        for task in tasks:
            task['_id'] = str(task['_id'])
            task['assigned_by'] = str(task['assigned_by'])
            task['assigned_user'] = str(task['assigned_user'])
            assigned_by_user = db.users.find_one({'_id': ObjectId(task['assigned_by'])})
            assigned_to_user = db.users.find_one({'_id': ObjectId(task['assigned_user'])})
            task['assigned_by_name'] = f"{assigned_by_user['first_name']} {assigned_by_user['last_name']}"
            task['assigned_to_name'] = f"{assigned_to_user['first_name']} {assigned_to_user['last_name']}"
            # Convert datetime objects to string
            if 'created_at' in task:
                task['created_at'] = task['created_at'].isoformat()

        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/task/<task_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def task_operations(task_id):
    try:
        current_user = get_jwt_identity()

        # Validate task_id format
        try:
            task_obj_id = ObjectId(task_id)
        except:
            return jsonify({'message': 'Invalid task ID format'}), 400

        if request.method == 'GET':
            task = db.tasks.find_one({
                '_id': task_obj_id,
                'assigned_user': current_user
            })

            if not task:
                return jsonify({'message': 'Task not found'}), 404

            task['_id'] = str(task['_id'])
            task['assigned_by'] = str(task['assigned_by'])
            task['assigned_user'] = str(task['assigned_user'])
            assigned_by_user = db.users.find_one({'_id': ObjectId(task['assigned_by'])})
            assigned_to_user = db.users.find_one({'_id': ObjectId(task['assigned_user'])})
            task['assigned_by_name'] = f"{assigned_by_user['first_name']} {assigned_by_user['last_name']}"
            task['assigned_to_name'] = f"{assigned_to_user['first_name']} {assigned_to_user['last_name']}"
            # Convert datetime objects to string
            if 'created_at' in task:
                task['created_at'] = task['created_at'].isoformat()

            return jsonify(task), 200

        elif request.method == 'PUT':
            data = request.get_json()
            if not data:
                return jsonify({'message': 'No input data provided'}), 400

            # Validate required fields
            required_fields = ['is_completed']
            if not all(field in data for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            task = db.tasks.find_one({'_id': task_obj_id, 'assigned_user': current_user})
            if not task:
                return jsonify({'message': 'Task not found'}), 404

            result = db.tasks.update_one(
                {'_id': task_obj_id, 'assigned_user': current_user},
                {'$set': {
                    'is_completed': data['is_completed'],
                    'updated_at': datetime.utcnow()
                }}
            )

            if result.modified_count == 0:
                return jsonify({'message': 'Task not found'}), 404

            assigned_by_user = db.users.find_one({'_id': ObjectId(task['assigned_by'])})
            assigned_to_user = db.users.find_one({'_id': ObjectId(task['assigned_user'])})
            notification_message = f"Task completed by {assigned_to_user['first_name']} {assigned_to_user['last_name']}"
            return jsonify({'message': 'Task updated successfully', 'notification': notification_message}), 200

        elif request.method == 'DELETE':
            task = db.tasks.find_one({'_id': task_obj_id, 'assigned_user': current_user})
            if not task:
                return jsonify({'message': 'Task not found'}), 404

            result = db.tasks.delete_one({
                '_id': task_obj_id,
                'assigned_user': current_user
            })

            if result.deleted_count == 0:
                return jsonify({'message': 'Task not found'}), 404

            return jsonify({'message': 'Task deleted successfully'}), 200

    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Fetch all users except the logged-in user
@app.route('/team', methods=['GET'])
@jwt_required()
def get_users():
    try:
        current_user = get_jwt_identity()
        users = list(db.users.find({'_id': {'$ne': ObjectId(current_user)}}))
        for user in users:
            user['_id'] = str(user['_id'])
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))
