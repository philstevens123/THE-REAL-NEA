from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super_secret_key_change_this_later'

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    profile = db.relationship('Profile', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Profile(db.Model):
    __tablename__ = 'profiles'
    id = db.Column(db.Integer, primary_key=True)
    bio = db.Column(db.String(120), nullable=False)
    top = db.Column(db.String(120), nullable=False)
    recent = db.Column(db.String(120), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

def load_data():
    if os.path.exists('games_db.json'):
        with open('games_db.json', 'r') as f:
            return json.load(f)
    return []



def filter_games(query):
    all_games = load_data()

    if query:
        filtered = [g for g in all_games if query in str(g).lower()]
    else:
        filtered = all_games[:5]  # Show only first 5 by default

    sorted_games = sorted(filtered, key=lambda x: x.get('title', '').lower())

    return sorted_games if query else sorted_games[:5]

@app.route('/')
def home():
    query = request.args.get('q', '').lower()
    filtered_games = filter_games(query)

    return render_template(
        'index.html',
        games=filtered_games,
        query=query
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('register'))

        existing_user = User.query.filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            flash("Username or Email already in use!")
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        return redirect(url_for('create_profile'))

    return render_template('create_account.html')


@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id

            if user.profile is None:
                flash("Account found, but no profile exists. Let's create one!")
                return redirect(url_for('create_profile'))

            flash("Welcome back!")
            return redirect(url_for('user_profile'))

        flash("Invalid username or password.")
        return redirect(url_for('sign_in'))

    return render_template('sign_in.html')


@app.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    user_id = session.get('user_id')

    if not user_id:
        flash("Please sign in first.")
        return redirect(url_for('sign_in'))

    if request.method == 'POST':
        new_profile = Profile(
            bio=request.form.get('bio'),
            top=request.form.get('top_5'),
            recent=request.form.get('recent'),
            user_id=user_id
        )

        db.session.add(new_profile)
        db.session.commit()

        return redirect(url_for('user_profile'))

    return render_template('create_profile.html')


@app.route('/user_profile')
def user_profile():
    user_id = session.get('user_id')

    if not user_id:
        flash("You must be logged in to view your profile.")
        return redirect(url_for('sign_in'))

    user = User.query.get(user_id)

    query = request.args.get('q', '').lower()
    filtered_games = filter_games(query)

    return render_template(
        'user_profile.html',
        user=user,
        games=filtered_games,
        query=query
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)