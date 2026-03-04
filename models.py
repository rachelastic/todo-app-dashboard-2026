from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    tasks = db.relationship('Task', backref='user')
    visits = db.relationship('Visit')  # added visits to user

    def set_password(self, password):
        """Hash the password and store it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check hashed password."""
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='not-completed')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def toggle(self):
        """Mark the task as done/undone."""
        self.status = 'completed' if self.status == 'not-completed' else 'not-completed'

    def __repr__(self):
        return f"<Task id={self.id} title='{self.title}' status={self.status}>"
    
    def to_dict(self):
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "user_id": self.user_id
        }


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(200), nullable=False)
    user = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True  # nullable so that we can log visits without a user
    )
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f"<Visit id={self.id} page='{self.page}' timestamp={self.timestamp}>"
    

class Waitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    ip_address = db.Column(db.String(45), nullable=True)

    def __repr__(self):
        return f"<Waitlist id={self.id} email='{self.email}' timestamp={self.timestamp}>"


class ErrorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(50), nullable=True)  # e.g. 'login', 'signup'
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f"<ErrorLog id={self.id} category='{self.category}' message='{self.message}'>"