from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Initialize Firebase Admin SDK with service account key file
cred = credentials.Certificate(os.path.join(os.path.dirname(__file__), 'turn.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()


def fetch_data(start_date, end_date):
    # Assuming you have a collection named 'main_routine' in Firestore
    routine_ref = db.collection('main_routine')
    # Query documents within the date range
    query = routine_ref.where('date', '>=', start_date).where('date', '<=', end_date).order_by('date')
    docs = query.stream()
    data = []
    for doc in docs:
        data.append(doc.to_dict())
    return data

def fetch_sub_data(start_date, end_date):
    # Assuming you have a collection named 'sub_routine' in your Firestore database
    sub_routine_ref = db.collection('sub_routine')
    
    # Query documents within the date range
    query = sub_routine_ref.where('date', '>=', start_date).where('date', '<=', end_date).order_by('date')
    docs = query.stream()
    
    sub_routine_data = []
    for doc in docs:
        sub_routine_data.append(doc.to_dict())
    
    return sub_routine_data


def calculate_cumulative_data(cumu_data):
    cumulative_day = [0, 0, 0, 0, 0]
    cumulative_carry = [1, 1, 1, 1, 1]
    
    for rec in cumu_data:
        for key in ['m1', 'm2', 'm3', 'm4', 'm5']:
            if rec[key] == 'D':
                index = int(key[1]) - 1  # Extract the index from the key (e.g., 'm1' -> 0)
                cumulative_day[index] += 1
                cumulative_carry[index] -= 1
    
    return list(zip(cumulative_day, cumulative_carry))


@app.route('/calculate_cumulative', methods=['POST'])
def calculate_cumulative():
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    cumulative_day = [0, 0, 0, 0, 0]
    cumulative_carry = [1, 1, 1, 1, 1]

    carpool_data = None  # Initialize carpool_data to None

    if start_date and end_date:
        carpool_data = fetch_data(start_date, end_date)  # Fetch carpool data
        for rec in carpool_data:
            for a, key in enumerate(['m1', 'm2', 'm3', 'm4', 'm5']):
                if rec[key] == 'D':
                    cumulative_day[a] += 1
                    cumulative_carry[a] -= 1

    cumulative_sub_day = [0, 0, 0, 0]
    cumulative_sub_carry = [1, 1, 1, 1]

    if start_date and end_date:
        sub_routine_data = fetch_sub_data(start_date, end_date)  # Fetch sub-routine data
        for rec in sub_routine_data:
            for a, key in enumerate(['m1', 'm2', 'm3', 'm4']):
                if rec[key] == 'D':
                    cumulative_sub_day[a] += 1
                    cumulative_sub_carry[a] -= 1

    # Calculate cumulative data for sub-routine
    cumulative_sub_data = list(zip(cumulative_sub_day, cumulative_sub_carry))

    # Pass cumulative data and carpool data to the template
    cumulative_data = list(zip(cumulative_day, cumulative_carry))

    # Pass cumulative data, carpool data, subroutine data, and sub-routine cumulative data to the template
    return render_template('cumulative.html', cumulative_data=cumulative_data, carpool_data=carpool_data, sub_routine_data=sub_routine_data, cumulative_sub_data=cumulative_sub_data, start_date=start_date, end_date=end_date)


def update_sub_routine(date, sub_driver):
    try:
        sub_routine_ref = db.collection('sub_routine').document(date)
        
        # Prepare data to update
        data = {'date': date}
        for col in ['m1', 'm2', 'm3', 'm4']:
            if col == sub_driver:
                data[col] = 'D'
            else:
                data[col] = 'P'

        # Update document
        sub_routine_ref.set(data)

        print("Sub routine updated successfully.")
    except Exception as e:
        print("Error:", e)

def update_carpool(date, driver, holiday, colleagues, sub_driver=None):
    try:
        main_routine_ref = db.collection('main_routine').document(date)
        
        # Check if the selected driver is marked as absent
        if any(colleague[0] == driver and not colleague[1] for colleague in colleagues):
            raise ValueError("The selected driver cannot be marked as absent.")

        # Prepare data to update for main routine
        main_routine_data = {'date': date}
        for col, absent in colleagues:
            main_routine_data[col] = 'A' if absent else 'P'
        driver = driver.lower()  # Convert driver to lowercase before assigning
        main_routine_data[driver] = 'D'
        
        # Set holiday status for main routine
        if holiday:
            for col in ['m1', 'm2', 'm3', 'm4', 'm5']:
                main_routine_data[col] = 'H'

        # Update main routine document
        main_routine_ref.set(main_routine_data)

        print("Main routine updated successfully.")

        # Update sub routine if driver is m5
        if driver == 'm5':
            update_sub_routine(date, sub_driver)  # Assume m1 is selected as sub-driver

    except ValueError as ve:
        print("Error:", ve)

@app.route('/delete', methods=['POST'])
def delete_record():
    date = request.form['date']
    
    # Delete record from main_routine collection
    main_routine_ref = db.collection('main_routine').document(date)
    main_routine_ref.delete()

    # Delete corresponding record from sub_routine collection
    sub_routine_ref = db.collection('sub_routine').document(date)
    sub_routine_ref.delete()

    flash("Record deleted successfully.")
    return redirect('/')


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date = request.form['date']
        driver = request.form['driver']
        holiday = 'holiday' in request.form  # Check if the holiday checkbox is checked
        colleagues = [('m1', 'm1' in request.form),
                      ('m2', 'm2' in request.form),
                      ('m3', 'm3' in request.form),
                      ('m4', 'm4' in request.form),
                      ('m5', 'm5' in request.form)]

        # If the driver is 'M5', get the selected sub-driver
        sub_driver = None
        if driver.lower() == 'm5':
            sub_driver = request.form['subDriver']

        update_carpool(date, driver, holiday, colleagues, sub_driver)

    main_routine_ref = db.collection('main_routine')
    carpool_data = [doc.to_dict() for doc in main_routine_ref.order_by('date').stream()]

    sub_routine_ref = db.collection('sub_routine')
    sub_routine_data = [doc.to_dict() for doc in sub_routine_ref.order_by('date').stream()]

    # Calculate cumulative day and carry data
    cumulative_data = calculate_cumulative_data(carpool_data)

    return render_template('index.html', carpool_data=carpool_data, cumulative_data=cumulative_data, sub_routine_data=sub_routine_data)

if __name__ == '__main__':
    app.run(debug=False)
