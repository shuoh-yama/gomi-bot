from . import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(100), unique=True, nullable=False)
    area_name = db.Column(db.String(100), db.ForeignKey('schedules.name'), nullable=True)
    
    schedule = db.relationship('Schedule', back_populates='users')

    def __repr__(self):
        return f'<User {self.line_user_id}>'

class Schedule(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    resources = db.Column(db.String(50))
    burnable = db.Column(db.String(50))
    ceramic_glass_metal = db.Column(db.String(50))

    users = db.relationship('User', back_populates='schedule')

    def __repr__(self):
        return f'<Schedule {self.name}>'
