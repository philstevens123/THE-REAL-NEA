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

#### DATABASE STUFF ####

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    profile = db.relationship('Profile', backref='user', uselist=False)
    reviews = db.relationship('Review', backref='author', lazy=True)

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

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(80), nullable=False)
    game_title = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # Store 1-100
    comment = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


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
        filtered = all_games[:5]
    sorted_games = sorted(filtered, key=lambda x: x.get('title', '').lower())
    return sorted_games if query else sorted_games[:5]

#### END OF DATABASE STUFF ####

#### ROUTE STUFF ####

@app.route('/')
def home():
    query = request.args.get('q', '').lower()
    filtered_games = filter_games(query)
    return render_template('index.html', games=filtered_games, query=query)

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

        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
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
                return redirect(url_for('create_profile'))
            return redirect(url_for('user_profile'))
        flash("Invalid username or password.")
    return render_template('sign_in.html')

@app.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    user_id = session.get('user_id')
    if not user_id:
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
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('sign_in'))

    query = request.args.get('q', '').lower()
    filtered_games = filter_games(query)

    return render_template('user_profile.html', user=user, games=filtered_games, query=query)

@app.route('/rate_game/<game_id>', methods=['POST'])
def rate_game(game_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to rate games.")
        return redirect(url_for('sign_in'))

    try:
        rating_val = int(request.form.get('rating'))
    except (ValueError, TypeError):
        flash("Invalid rating.")
        return redirect(url_for('user_profile'))

    if rating_val < 1 or rating_val > 100:
        flash("Rating must be between 1 and 100.")
        return redirect(url_for('user_profile'))

    comment = request.form.get('comment')
    game_title = request.form.get('game_title')

    # Check for existing review to update, else create new
    existing = Review.query.filter_by(user_id=user_id, game_id=game_id).first()
    if existing:
        existing.rating = rating_val
        existing.comment = comment
        flash(f"Updated review for {game_title}!")
    else:
        new_rev = Review(game_id=game_id, game_title=game_title, rating=rating_val, 
                         comment=comment, user_id=user_id)
        db.session.add(new_rev)
        flash(f"Submitted review for {game_title}!")

    db.session.commit()
    return redirect(url_for('user_profile'))

#### END OF ROUTES STUFF ####

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)