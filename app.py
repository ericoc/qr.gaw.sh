from flask import Flask, render_template, send_from_directory, request, make_response
import secrets
import re
from influxdb import InfluxDBClient

app = Flask(__name__)

"""
Main page
"""
@app.route('/')
@app.route('/submit', methods=['GET'])
def display_survey():

    # Thank them if they have already completed the survey
    if request.cookies and 'user_name' in request.cookies and re.match("^[a-zA-Z ']+$", request.cookies.get('user_name')):
        return render_template('thanks.html.j2', name=request.cookies.get('user_name'))

    # Otherwise, allow them to complete the survey
    else:
        return render_template('survey.html.j2')

"""
Show cookies
"""
@app.route('/cookies/show', methods=['GET'])
def show_cookies():

    # Loop through and display all of the cookies in the current request
    if request.cookies:
        body = '<pre>'
        for cookie in request.cookies.items():
            body += f"{cookie}<br>\n"
        body += '</pre>'
    else:
        body = 'No cookies'

    response = make_response(body)
    return response

"""
Clear cookies
# Also used by error handler for 400 and 500 responses
"""
@app.route('/cookies/clear', methods=['GET'])
def clear_cookies(cookies=None, myresponse=None):

    # Get the current request cookies if they were not passed in
    if not cookies:
        cookies = request.cookies

    # Make a simple "OK" response if one was not passed in (i.e. not being called from errorhandler)
    if not myresponse:
        myresponse = make_response('OK')

    # Loop through each cookie wiping them out
    for cookie in cookies.keys():
        myresponse.delete_cookie(cookie)

    # Return our final response wiping out all the cookies
    return myresponse

"""
Handle HTTP 400 and 500 error responses while clearing cookies
"""
@app.errorhandler(400)
@app.errorhandler(500)
def error_page(message=None, code=500):
    response = make_response(render_template('sorry.html.j2', error_message=message), code)
    return clear_cookies(cookies=request.cookies, myresponse=response)

"""
Handle HTTP 404 error responses
"""
@app.errorhandler(404)
def lost(message='Page not found'):
    return make_response(render_template('sorry.html.j2', error_message=message), 404)

"""
Handle HTTP 405 error responses
"""
@app.errorhandler(405)
def nicetry(message='Method not allowed'):
    return make_response(render_template('sorry.html.j2', error_message=message), 405)

"""
Handle new survey form submissions
"""
@app.route('/submit', methods=['POST'])
def submit_survey():

    # If they have a cookie, they have already completed the survey - so just thank them for doing so
    if request.cookies and 'user_name' in request.cookies and re.match("^[a-zA-Z ']+$", request.cookies.get('user_name')):
        return render_template('thanks.html.j2', name=request.cookies.get('user_name'))

    # New form submissions need processed
    elif request.form:

        # Validate the name
        if 'user_name' in request.form and re.match("^[a-zA-Z ']+$", request.form['user_name']):
            name = request.form['user_name']
        else:
            return error_page(message='Please enter a valid name', code=400)

        # Validate the e-mail address and make sure it is lowercase
        if 'user_email' in request.form and re.match('^[a-zA-Z0-9_\-\+]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,6}$', request.form['user_email']):
            email = request.form['user_email'].lower()
        else:
            return error_page(message='Please enter a valid e-mail address', code=400)

        # Begin building a response and setting cookies for the user to accept their survey entry
        cookie_expiration = 86400*30
        response = make_response(render_template('thanks.html.j2', name=name))
        response.set_cookie('user_name', name, max_age=cookie_expiration)
        response.set_cookie('user_email', email, max_age=cookie_expiration)

        # Validate the telephone number, if one was given
        if 'user_phone' in request.form and request.form['user_phone'] != '':
            if re.match('^[0-9\-\+\(\)\.]+', request.form['user_phone']):
                phone = re.sub('[^0-9]', '', request.form['user_phone'])
                response.set_cookie('user_phone', phone, max_age=cookie_expiration)
            else:
                return error_page(message='Please enter a valid telephone number', code=400)
        else:
            phone = None

        # Turn locations details into floating point numbers for InfluxDB, but...
        # ...store values in cookies as strings
        try:
            if 'user_latitude' in request.form:
                latitude = float(request.form['user_latitude'])
                response.set_cookie('user_latitude', str(latitude), max_age=cookie_expiration)

            if 'user_longitude' in request.form:
                longitude = float(request.form['user_longitude'])
                response.set_cookie('user_longitude', str(longitude), max_age=cookie_expiration)

            if 'user_accuracy' in request.form:
                accuracy = float(request.form['user_accuracy'])
                response.set_cookie('user_accuracy', str(accuracy), max_age=cookie_expiration)

        except Exception as e:
            print(e)
            return error_page(message='There was an error determining your location eligibility', code=400)

        # Connect to InfluxDB
        try:
            client = InfluxDBClient(host='127.0.0.1', port=8086, username=secrets.db_username, password=secrets.db_password, ssl=False, verify_ssl=False)

        except Exception as e:
            print(e)
            return error_page(message='Cannot connect to database', code=500)

        # Check that the e-mail address has not already been added to InfluxDB in the past day
        try:
            client.switch_database(secrets.db_database)
            find_email = f"SELECT \"name\" FROM \"{secrets.db_database}\" WHERE email = '\"{email}\"' AND time > now() - 1d LIMIT 1"
            results = client.query(find_email)

            if (len(results.items())) > 0:
                return error_page(message='Please limit yourself to one entry per day', code=425)

        except:
            print(e)
            return error_page(message='There was an error determining your e-mail eligibility', code=500)

        # Insert the data to InfluxDB
        try:
            write_data = f"{secrets.db_database},email=\"{email}\" name=\"{name}\",ip=\"{request.remote_addr}\",latitude={latitude},longitude={longitude},accuracy={accuracy}"

            # Include the phone number in InfluxDB, if one was given
            if phone:
                write_data +=f",phone={phone}"

            if client.write(write_data, params={'db': secrets.db_database}, protocol='line'):
                return response

        except Exception as e:
            print(e)
            return error_page(message='Cannot write to database', code=500)

    else:
        return error_page(message='Invalid request', code=400)


if __name__ == "__main__":
    app.run()
