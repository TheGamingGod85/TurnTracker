'''
The main file of this Flask web application serves as the central hub for various functionalities.
It encapsulates the core code for managing the main routine, sub-routine, and the accumulation of daily and carryover data.
Within its structure, there are provisions for updating and deleting records from these collections, ensuring robust data management.
Additionally, it handles the intricacies of user authentication with routes dedicated to login and logout, as well as an index route tailored for both editors and visitors.
Furthermore, the file encompasses logic for retrieving data based on specified date ranges and calculating cumulative statistics for the main and sub-routines accordingly.
Moreover, it incorporates essential components such as the User class and the login manager for Flask-Login,
along with the necessary functions for user loading and authentication routes.
This comprehensive integration within the main file ensures the smooth functioning and security of the Flask web application.
'''



# Import required libraries
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask import Flask, render_template, request, flash, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore
import os
import webview



# Initialize Flask app
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'    # Secret key for flash messages



# Create window for webview
window = webview.create_window("Carpool System", app)



# Initialize Firebase Admin SDK with service account key file
cred = credentials.Certificate(os.path.join(os.path.dirname(__file__), 'turn.json'))    # Service account key file
firebase_admin.initialize_app(cred)   # Initialize Firebase Admin SDK
db = firestore.client()   # Initialize Firestore database



# Initialize Flask-Login
login_manager = LoginManager()  # Login manager
login_manager.init_app(app) # Initialize login manager



# ------------------- Flask-Login Start -------------------   
class User(UserMixin):  # User class
    def __init__(self, id): # Constructor
        self.id = id    # User ID


@login_manager.user_loader  # User loader
def load_user(user_id): # Load user
    user_doc = db.collection('users').document(user_id).get()   # Get user document
    if user_doc.exists: # If user document exists
        return User(user_id)    # Return user
    else:   # If user document does not exist
        return None   # Return None


@app.route('/login', methods=['GET', 'POST'])   # Login route
def login():    # Login function
    if request.method == 'POST':    # If request method is POST
        username = request.form['username']   # Get username
        password = request.form['password']   # Get password
        user_doc = db.collection('users').document(username).get()  # Get user document
        if user_doc.exists and user_doc.to_dict()['passwd'] == password:    # If user document exists and password is correct
            user = User(username)   # Create user
            login_user(user)    # Login user
            return redirect(url_for('index'))   # Redirect to index route
        else:
            error = "Invalid Username or Password"   # If user document does not exist or password is incorrect
            return redirect(url_for('login') + '?error=' + error)   # Redirect to login route
    return render_template('login.html')    # Render login template


@app.route('/logout')   # Logout route
@login_required  # Login required
def logout():   # Logout function
    logout_user()   # Logout user
    return redirect(url_for('login'))   # Redirect to login route
# ------------------- Flask-Login End -------------------



# ------------------- Flask Index Start -------------------
@app.route('/', methods=['GET', 'POST'])    # Index route for Editor
def index():    # Index function
    if current_user.is_authenticated:   # If user is authenticated
        if request.method == 'POST':    # If request method is POST
            date = request.form['date'] # Get date
            driver = request.form['driver'] # Get driver
            holiday = 'holiday' in request.form  # Check if the holiday checkbox is checked
            colleagues = [('m1', 'm1' in request.form),
                          ('m2', 'm2' in request.form),
                          ('m3', 'm3' in request.form),
                          ('m4', 'm4' in request.form),
                          ('m5', 'm5' in request.form)] # Get colleagues

            # If the driver is 'M5', get the selected sub-driver
            sub_driver = None   # Initialize sub_driver to None
            if driver.lower() == 'm5':
                sub_driver = request.form['subDriver']

            update_carpool(date, driver, holiday, colleagues, sub_driver)   # Update carpool data

        main_routine_ref = db.collection('main_routine')    # Main routine reference
        carpool_data = [doc.to_dict() for doc in main_routine_ref.order_by('date').stream()]

        sub_routine_ref = db.collection('sub_routine')  # Sub routine reference
        sub_routine_data = [doc.to_dict() for doc in sub_routine_ref.order_by('date').stream()] 

        # Calculate cumulative day and carry data
        cumulative_data = calculate_cumulative_data(carpool_data)

        return render_template('index.html', carpool_data=carpool_data, cumulative_data=cumulative_data, sub_routine_data=sub_routine_data)  # Render index template
    else:   # If user is not authenticated
        return redirect(url_for('login'))   # Redirect to login route


@app.route('/visit', methods=['GET', 'POST'])   # Index route for Visitor
def visit():    # Visit function
    main_routine_ref = db.collection('main_routine')    # Main routine reference
    carpool_data = [doc.to_dict() for doc in main_routine_ref.order_by('date').stream()]

    sub_routine_ref = db.collection('sub_routine')  # Sub routine reference
    sub_routine_data = [doc.to_dict() for doc in sub_routine_ref.order_by('date').stream()]

    # Calculate cumulative day and carry data
    cumulative_data = calculate_cumulative_data(carpool_data)

    return render_template('index_visitor.html', carpool_data=carpool_data, cumulative_data=cumulative_data, sub_routine_data=sub_routine_data) # Render index template for visitor
# ------------------- Flask Index End -------------------



# ------------------- Flask Fetch Data Start -------------------
def fetch_data(start_date, end_date):   # Fetch Data (Main Routine)

    routine_ref = db.collection('main_routine') # Main routine reference
    query = routine_ref.where('date', '>=', start_date).where('date', '<=', end_date).order_by('date')  # Query documents within the date range
    docs = query.stream()   # Stream documents
    data = []   # Initialize data to empty list
    # Append documents to data list
    for doc in docs:
        data.append(doc.to_dict())

    return data # Return data


def fetch_sub_data(start_date, end_date):   # Fetch Data (Sub Routine)

    sub_routine_ref = db.collection('sub_routine')  # Sub routine reference
    
    # Query documents within the date range
    query = sub_routine_ref.where('date', '>=', start_date).where('date', '<=', end_date).order_by('date')  # Query documents within the date range
    docs = query.stream()   # Stream documents
    
    sub_routine_data = []   # Initialize sub_routine_data to empty list
    # Append documents to sub_routine_data list
    for doc in docs:
        sub_routine_data.append(doc.to_dict())
    
    return sub_routine_data  # Return sub_routine_data
# ------------------- Flask Fetch Data End -------------------



# ------------------- Flask Cumulative Start -------------------
def calculate_cumulative_data(cumu_data):   # Calculate Cumulative (All Data)

    cumulative_day = [0, 0, 0, 0, 0]    # Initialize cumulative_day to [0, 0, 0, 0, 0]
    cumulative_carry = [1, 1, 1, 1, 1]  # Initialize cumulative_carry to [1, 1, 1, 1, 1]
    
    for rec in cumu_data:   # Iterate through each record in cumu_data
        for key in ['m1', 'm2', 'm3', 'm4', 'm5']:  # Iterate through each key in ['m1', 'm2', 'm3', 'm4', 'm5']
            if rec[key] == 'D': # If the value of the key is 'D'
                index = int(key[1]) - 1  # Extract the index from the key (e.g., 'm1' -> 0)
                cumulative_day[index] += 1  # Increment the value at the index in cumulative_day
                cumulative_carry[index] -= 1    # Decrement the value at the index in cumulative_carry
    
    return list(zip(cumulative_day, cumulative_carry))  # Return a list of tuples of cumulative_day and cumulative_carry


@app.route('/calculate_cumulative', methods=['POST'])   # Calculate Cumulative (Main Routine and Sub Routine) According to Date Range
def calculate_cumulative(): # Calculate Cumulative function

    start_date = request.form.get('start_date')  # Get start date
    end_date = request.form.get('end_date') # Get end date

    cumulative_day = [0, 0, 0, 0, 0]    # Initialize cumulative_day to [0, 0, 0, 0, 0]
    cumulative_carry = [1, 1, 1, 1, 1]  # Initialize cumulative_carry to [1, 1, 1, 1, 1]

    carpool_data = None  # Initialize carpool_data to None

    if start_date and end_date: # If start_date and end_date are not None
        carpool_data = fetch_data(start_date, end_date)  # Fetch carpool data
        for rec in carpool_data:    # Iterate through each record in carpool_data
            for a, key in enumerate(['m1', 'm2', 'm3', 'm4', 'm5']):    # Iterate through each key in ['m1', 'm2', 'm3', 'm4', 'm5']
                if rec[key] == 'D': # If the value of the key is 'D'
                    cumulative_day[a] += 1  # Increment the value at the index in cumulative_day
                    cumulative_carry[a] -= 1    # Decrement the value at the index in cumulative_carry

    cumulative_sub_day = [0, 0, 0, 0]   # Initialize cumulative_sub_day to [0, 0, 0, 0]
    cumulative_sub_carry = [1, 1, 1, 1] # Initialize cumulative_sub_carry to [1, 1, 1, 1]

    if start_date and end_date: # If start_date and end_date are not None
        sub_routine_data = fetch_sub_data(start_date, end_date)  # Fetch sub-routine data
        for rec in sub_routine_data:    # Iterate through each record in sub_routine_data
            for a, key in enumerate(['m1', 'm2', 'm3', 'm4']):  # Iterate through each key in ['m1', 'm2', 'm3', 'm4']
                if rec[key] == 'D': # If the value of the key is 'D'
                    cumulative_sub_day[a] += 1  # Increment the value at the index in cumulative_sub_day
                    cumulative_sub_carry[a] -= 1    # Decrement the value at the index in cumulative_sub_carry

    # Calculate cumulative data for sub-routine
    cumulative_sub_data = list(zip(cumulative_sub_day, cumulative_sub_carry))

    # Pass cumulative data and carpool data to the template
    cumulative_data = list(zip(cumulative_day, cumulative_carry))

    # Pass cumulative data, carpool data, subroutine data, and sub-routine cumulative data to the template
    return render_template('cumulative.html', cumulative_data=cumulative_data, carpool_data=carpool_data, sub_routine_data=sub_routine_data, cumulative_sub_data=cumulative_sub_data, start_date=start_date, end_date=end_date)

# ------------------- Flask Cumulative End -------------------



# ------------------- Flask Update Start -------------------
def update_sub_routine(date, sub_driver, colleagues):   # Update Sub Routine
    try:    # Try block
        sub_routine_ref = db.collection('sub_routine').document(date)   # Sub routine reference

        data = {'date': date}   # Initialize data to {'date': date}
        for col, absent in colleagues:    # Iterate through each colleague and their absent status
            if col == sub_driver:   # If the colleague is the sub-driver
                data[col] = 'D' if not absent else 'A'  # Set the value of the column to 'D' if not absent, else 'A'
            else:
                data[col] = 'A' if absent else 'P'  # Set the value of the column to 'A' if absent, else 'P'

        sub_routine_ref.set(data)   # Set data

        print("Sub routine updated successfully.")  # Print success message
    except Exception as e:  # Catch exception
        print("Error:", e)  # Print error message


def update_carpool(date, driver, holiday, colleagues, sub_driver=None):    # Update Main Routine
    try:    # Try block
        main_routine_ref = db.collection('main_routine').document(date)  # Main routine reference
        
        if any(colleague[0] == driver and not colleague[1] for colleague in colleagues):    # If the selected driver cannot be marked as absent
            raise ValueError("The selected driver cannot be marked as absent.")  # Raise ValueError

        # Prepare data to update for main routine
        main_routine_data = {'date': date}  # Initialize main_routine_data to {'date': date}
        for col, absent in colleagues:  # Iterate through each column and absent in colleagues
            main_routine_data[col] = 'A' if absent else 'P' # Set the value of the column to 'A' if absent is True, else 'P'
        driver = driver.lower()  # Convert driver to lowercase before assigning to main_routine_data
        main_routine_data[driver] = 'D'   # Set the value of the driver to 'D'
        
        # Set holiday status for main routine
        if holiday: # If holiday is True
            for col in ['m1', 'm2', 'm3', 'm4', 'm5']:  # Iterate through each column in ['m1', 'm2', 'm3', 'm4', 'm5']
                main_routine_data[col] = 'H'    # Set the value of the column to 'H'

        # Update main routine document
        main_routine_ref.set(main_routine_data)

        print("Main routine updated successfully.") # Print success message

        # Update sub routine if driver is m5
        if driver == 'm5':  # If driver is m5
            update_sub_routine(date, sub_driver, colleagues)    # Update sub routine

    except ValueError as ve:    # Catch ValueError
        print("Error:", ve) # Print error message
# ------------------- Flask Update End -------------------



# ------------------- Flask Delete Record Start -------------------
@app.route('/delete', methods=['POST'])   # Delete Record
def delete_record():    # Delete Record function
    date = request.form['date'] # Get date
    
    # Delete record from main_routine collection
    main_routine_ref = db.collection('main_routine').document(date) # Main routine reference
    main_routine_ref.delete()   # Delete record

    # Delete corresponding record from sub_routine collection
    sub_routine_ref = db.collection('sub_routine').document(date)   # Sub routine reference
    sub_routine_ref.delete()    # Delete record

    flash("Record deleted successfully.")   # Flash success message
    return redirect('/')    # Redirect to index route
# ------------------- Flask Delete Record End -------------------


if __name__ == '__main__':  # Run the app
    # app.run(debug=True) # Run the app in debug mode
    # app.run(host='0.0.0.0', port=5000)  # Run the app on port 5000
    webview.start() # Start webview