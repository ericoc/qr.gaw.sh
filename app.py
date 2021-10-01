from flask import Flask, render_template, send_from_directory, request, make_response, url_for, redirect

app = Flask(__name__)

@app.route('/')
def display_survey():
    return render_template('survey.html.j2')

@app.route('/submit', methods=['POST'])
def submit_survey():
    return render_template('thanks.html.j2',
        name = request.form['user_name'],
        email = request.form['user_email'],
        phone = request.form['user_phone'],
        ip_address = request.remote_addr,
        user_agent = request.user_agent,
        latitude = request.form['user_latitude'],
        longitude = request.form['user_longitude'],
        accuracy = request.form['user_accuracy']
    )

@app.route('/icon.png', methods=['GET'])
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

if __name__ == "__main__":
    app.run()
