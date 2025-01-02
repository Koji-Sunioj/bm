import psycopg2
import psycopg2.extras
from passlib.context import CryptContext
from flask import Flask, render_template, request, redirect, flash, session

# hello you

conn = psycopg2.connect(database="blackmetal",
                        host="localhost",
                        user="bm_admin",
                        password="18cba9cd-0776-4f09-9c0e-41d2937fab2b",
                        port=5432)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


app = Flask(__name__)
app.secret_key = "123456"


@app.route('/')
def index():
    print(session)
    return render_template('index.html')


@app.route('/my-account')
def my_account():
    if "username" in session:
        cursor.callproc("get_user", (session["username"], "cart"))
        user = cursor.fetchone()["bm_user"]
        return render_template("my-account.html", user=user)
    else:
        return "<h2>please log in </h2>"


@app.route('/sign-in', methods=["GET", "POST"])
def login():
    match request.method:
        case "GET":
            return render_template('sign-in.html')
        case "POST":
            try:
                cursor.callproc(
                    "get_user", (request.form["username"], "password"))
                user = cursor.fetchone()["bm_user"]
                verified = pwd_context.verify(
                    request.form["password"], user["password"])
                if not verified:
                    raise Exception()
                session["username"] = user["username"]
                return redirect("/my-account")
            except:
                return render_template('sign-in.html', response="invalid credentials")


@app.route('/albums')
def hello():
    sort = request.args.get('sort')
    direction = request.args.get('direction')
    page = request.args.get('page')
    search = request.args.get('search')

    valid_params = all([sort, direction, page])

    if not valid_params:
        return redirect("/albums?sort=title&direction=ascending&page=1")

    if search == "":
        return redirect("/albums?sort=%s&direction=%s&page=%s" % (sort, direction, page))

    sorts = []
    for sortable in ["price", "stock", "title", "release_year", "name"]:
        selected = " selected" if sortable == sort else ""
        sorts.append(
            f'<option value="{sortable}"{selected}>{" ".join(sortable.split("_"))}</option>')

    try:
        cursor.callproc("get_albums", (page, sort, direction, search))

        data = cursor.fetchall()
        cursor.callproc("get_pages", ("albums", search))

        n_pages, page_index = cursor.fetchone()["pages"], 0
        pages = []

        while page_index < n_pages:
            page_index = page_index + 1
            href_query = "" if search == None else "&search=%s" % (search)
            href = "/albums?sort=%s&direction=%s&page=%s" % (
                sort, direction, page_index) + href_query

            pages.append({"page": page_index, "href": href})

        params = {"sort": sort, "direction": direction,
                  "search": search, "page": page}

        return render_template('albums.html', data=data, search=search or "", sorts=sorts, direction=direction, pages=pages, params=params)
    except Exception as e:
        conn.rollback()
        return "<h1>there was an error %s</h2>" % e, 400
