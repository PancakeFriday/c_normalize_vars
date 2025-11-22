from flask import Flask, render_template, request, jsonify
from converter import convert_code

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert():
    data = request.json
    base = data.get("base", "")
    source = data.get("source", "")

    try:
        result = convert_code(base, source)
        return jsonify({ "output": result })
    except Exception as e:
        return jsonify({ "output": "Error: " + str(e) })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
