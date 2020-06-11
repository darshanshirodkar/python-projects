from flask import Flask, render_template
app = Flask(__name__)

projects = [{'author':'darshan',
				'project': 'flask website'},
			{'author':'doctor',
				'project': 'doctor who'}
			]

@app.route("/")
def hello():
	return render_template('home.html', projects = projects, title = "DS")

@app.route("/about")
def abt():
	return render_template('about.html')

if __name__ == '__main__':
	app.run(debug=True)