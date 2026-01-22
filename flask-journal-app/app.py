from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
# This creates a local file named 'journal.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///journal.db'
db = SQLAlchemy(app)

# Database Model
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Fetch all entries, newest first
    entries = Entry.query.order_by(Entry.date_posted.desc()).all()
    return render_template('index.html', entries=entries)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        new_entry = Entry(
            title=request.form['title'],
            content=request.form['content']
        )
        db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('create.html')

if __name__ == '__main__':
    app.run(debug=True)
