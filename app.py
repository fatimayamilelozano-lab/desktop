from flask import Flask, render_template, request, redirect, url_for, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = 'planta_pro_ultra_2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///planta_v5_final.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ADMIN_PASSWORD = "1234" 

class Operacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operario = db.Column(db.String(100))
    estacion = db.Column(db.String(100))
    capacidad_neta = db.Column(db.Float)
    peso_kg = db.Column(db.Float)
    costo_total_op = db.Column(db.Float)
    incidencia = db.Column(db.String(200))
    minutos_paro = db.Column(db.Integer, default=0)
    fecha = db.Column(db.DateTime, default=datetime.now)
    activo = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = session.get('admin_autenticado', False)
    if request.method == 'POST':
        try:
            op = request.form.get('operario', '').upper()
            est = request.form.get('nombre', '').upper()
            tiempos = [float(t.strip()) for t in request.form.get('tiempos', '0').split(',') if t.strip()] or [0]
            p_sem = float(request.form.get('tarifa') or 0)
            peso = float(request.form.get('peso_kg') or 0)
            p_kilo = float(request.form.get('pago_kilo') or 0)
            m_paro = int(request.form.get('minutos_paro') or 0)
            
            t_est = (sum(tiempos)/len(tiempos)) * 1.15
            p_hr = 60 / t_est if t_est > 0 else 0
            costo = ((p_sem / 48) / p_hr if p_hr > 0 else 0) + (peso * p_kilo)
            
            nueva = Operacion(operario=op, estacion=est, capacidad_neta=round(p_hr, 2), 
                              peso_kg=peso, costo_total_op=round(costo, 2), 
                              incidencia=request.form.get('incidencia', 'Normal'),
                              minutos_paro=m_paro)
            db.session.add(nueva)
            db.session.commit()
        except: pass
        return redirect(url_for('index'))

    regs = Operacion.query.filter_by(activo=True).all()
    dat_c = db.session.query(Operacion.operario, db.func.sum(Operacion.costo_total_op)).filter_by(activo=True).group_by(Operacion.operario).all()
    res = {"cuello": min(regs, key=lambda x: x.capacidad_neta).estacion if regs else "N/A",
           "total_k": round(sum(r.peso_kg for r in regs), 2), 
           "total_c": round(sum(r.costo_total_op for r in regs), 2)}
    
    return render_template('index.html', registros=regs, resumen=res, admin=admin,
                           l_costos=[d[0] for d in dat_c], v_costos=[d[1] for d in dat_c])

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('password') == ADMIN_PASSWORD: session['admin_autenticado'] = True
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('admin_autenticado', None)
    return redirect(url_for('index'))

@app.route('/historial')
def historial():
    todos = Operacion.query.order_by(Operacion.fecha.desc()).all()
    return render_template('historial.html', registros=todos)

@app.route('/exportar_excel')
def exportar_excel():
    registros = Operacion.query.all()
    if not registros: return "No hay datos", 404
    df = pd.DataFrame([{"Fecha": r.fecha.strftime('%d/%m/%Y %H:%M'), "Operario": r.operario, "Estación": r.estacion, 
                        "Pzas/H": r.capacidad_neta, "Kilos": r.peso_kg, "Costo ($)": r.costo_total_op, 
                        "Incidencia": r.incidencia, "Minutos Paro": r.minutos_paro} for r in registros])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Produccion')
    output.seek(0)
    return send_file(output, download_name="Reporte_Industrial.xlsx", as_attachment=True)

@app.route('/cerrar_turno_reporte')
def cerrar_turno_reporte():
    if not session.get('admin_autenticado'): return redirect(url_for('index'))
    regs = Operacion.query.filter_by(activo=True).all()
    rep = {"kilos": sum(r.peso_kg for r in regs), "inversion": sum(r.costo_total_op for r in regs),
           "minutos_perdidos": sum(r.minutos_paro for r in regs)}
    Operacion.query.filter_by(activo=True).update({Operacion.activo: False})
    db.session.commit()
    return render_template('reporte_cierre.html', r=rep)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
