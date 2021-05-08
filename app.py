# from venv import logger
from flask import Flask, render_template, request, redirect, flash
import sys
import requests
import pytemperature
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils.functions import database_exists
from sqlalchemy.exc import SQLAlchemyError
import logging
import secrets
from datetime import datetime

# Init Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
db = SQLAlchemy(app)

secret = secrets.token_urlsafe(32)
app.secret_key = secret


# Create database table
class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return '<City %r>' % self.name


def calculate_session_from_day(hour):
    session = ""
    if 0 <= hour <= 6:
        session = 'evening-morning'
    elif 6 < hour <= 18:
        session = 'day'
    else:
        session = 'night'
    return session


# decorator function for add or update data
def db_persist(func):
    def persist(*args, **kwargs):
        func(*args, **kwargs)
        try:
            db.session.commit()
            logging.info("success calling db func: " + func.__name__)
            return True
        except SQLAlchemyError as e:
            logging.error(e.args)
            flash('The city has already been added to the list!')
            db.session.rollback()
            return False

    return persist


@db_persist
def insert_or_update(object):
    return db.session.merge(object)


@app.route('/delete/<city_id>', methods=['GET', 'POST'])
def delete(city_id):
    city = City.query.filter_by(id=city_id).first()
    db.session.delete(city)
    db.session.commit()
    return redirect('/')


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    cities_db = []
    cities = []
    open_weather_api = 'cae05ad376ffb1c2738131d97f06b3a0'
    if request.method == 'POST':
        city_name = None
        city_name = str(request.form['city_name']).strip()
        r = requests.get(
            'http://api.openweathermap.org/data/2.5/weather?q={0}&appid={1}'.format(city_name.replace(' ', ''),
                                                                                    open_weather_api))
        if r:
            city = City(name=city_name.upper())
            insert_or_update(city)

        else:
            flash("The city doesn't exist!")
        redirect('/')

    # get all database
    if not database_exists('sqlite:///weather.db'):
        db.create_all()

    # get utc timestamp
    utc = datetime.utcnow()
    utc_timestamp = datetime.timestamp(utc)

    # query all cities
    cities_db = City.query.all()
    for city in cities_db:
        r = requests.get(
            'http://api.openweathermap.org/data/2.5/weather?q={0}&appid={1}'.format(city.name.replace(' ', ''),
                                                                                    open_weather_api))
        if r:
            # parser data to json
            weather_value = r.json()
            # calculate kalvin to celsius
            celsius = int(pytemperature.k2c(int(weather_value['main']['temp'])))
            # calculate session in a day
            city_timezone = weather_value['timezone']
            city_timestamp = utc_timestamp + city_timezone
            city_time = datetime.fromtimestamp(city_timestamp)
            session = calculate_session_from_day(city_time.hour)

            # append dictionary to list
            cities.append({
                'id': city.id,
                'name': city.name,
                'temp': celsius,
                'weather_state': weather_value['weather'][0]['main'],
                'time': '{} : {}'.format(city_time.hour, city_time.minute),
                'session_day': session
            })

    return render_template('index.html', cities=cities)


# don't change the following way to run flask:
if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg_host, arg_port = sys.argv[1].split(':')
        app.run(host=arg_host, port=arg_port)

    else:
        app.run()
