from flask import Flask

app = Flask(_name_)

@app.route('/')
  return "Hello railway"

if _name_ == 'main':
  app.run(debug=True, host="0.0.0.0", port = 5000)
