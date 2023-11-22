from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_socketio import SocketIO, emit  # Ajout de cette ligne
import sqlite3
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from waitress import serve
import schedule
import time
import threading
import tkinter as tk
from tkinter import messagebox


app = Flask(__name__)
app.secret_key = 'your_secret_key'  
DATABASE = 'westnest.db'
socketio = SocketIO(app)  


def check_inactive_users():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    threshold = datetime.now() - timedelta(minutes=30)
    cur.execute("SELECT user_id FROM OnlineUsers WHERE last_activity < ?", (threshold,))
    inactive_users = [row[0] for row in cur.fetchall()]
    cur.executemany("INSERT OR REPLACE INTO OnlineUsers (user_id, is_online) VALUES (?, 0)", [(user_id,) for user_id in inactive_users])
    conn.commit()
    conn.close()
schedule.every(5).minutes.do(check_inactive_users)

def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

def create_table():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS Subgroup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_subgroup TEXT NOT NULL,
        types_service TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS Utilisateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_utilisateur TEXT NOT NULL,
        email TEXT NOT NULL,
        mot_de_passe TEXT NOT NULL,
        id_subgroup INTEGER NOT NULL,
        FOREIGN KEY (id_subgroup) REFERENCES Subgroup(id)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS TodoList (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_utilisateur INTEGER NOT NULL,
    tache TEXT NOT NULL,
    etat TEXT NOT NULL, -- Ajout de l'étape
    priorite INTEGER NOT NULL,
    deadline DATE, -- Ajout de la date d'échéance
    types_services TEXT,
    FOREIGN KEY (id_utilisateur) REFERENCES Utilisateurs(id)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS OnlineUsers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        is_online INTEGER NOT NULL DEFAULT 0, 
        last_activity DATETIME,
        FOREIGN KEY (user_id) REFERENCES Utilisateurs(id)
    )''') 
    cur.execute('''CREATE TABLE IF NOT EXISTS Projet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_projet TEXT NOT NULL,
    description TEXT,
    date_debut DATE,
    date_fin DATE,
    responsable_id INTEGER, -- ID de l'utilisateur responsable
    etat_projet TEXT,
    budget REAL,
    FOREIGN KEY (responsable_id) REFERENCES Utilisateurs(id)
        )''') 
    cur.execute('''CREATE TABLE IF NOT EXISTS ProjetMembres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projet_id INTEGER,
        utilisateur_id INTEGER,
        FOREIGN KEY (projet_id) REFERENCES Projet(id),
        FOREIGN KEY (utilisateur_id) REFERENCES Utilisateurs(id)
        )''') 
    cur.execute('''CREATE TABLE IF NOT EXISTS ProjetTaches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projet_id INTEGER,
        tache_id INTEGER,
        FOREIGN KEY (projet_id) REFERENCES Projet(id),
        FOREIGN KEY (tache_id) REFERENCES TodoList(id)
    )''')  

    conn.commit()
    conn.close()

create_table()

def insert_subgroups():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.execute("INSERT INTO Subgroup (nom_subgroup, types_service) VALUES (?, ?)", ("NFTeam - Head", "Administration, Gestion des Ressources Humaines, Stratégie Marketing, Analyse de Marché, Prise de Décisions Stratégiques, Planification Financière, Communication d'Entreprise, Relations Publiques, Développement Commercial, Supervision des Opérations, Élaboration de Politiques Internes, Recherche de Partenariats, Évaluation des Performances, Gestion de Projet, Élaboration de Budget, Formation du Personnel, Développement Organisationnel, Planification Stratégique."))

    subgroup_data = [
    ("NFTeam - Développement", "Développement Web, Développement d'Applications, Programmation Backend, Programmation Frontend"),
    ("NFTeam - Graphisme", "Conception Graphique, Illustration, Animation, Design d'Interface Utilisateur"),
    ("NFTeam - Réseaux", "Gestion de Réseaux, Sécurité Informatique, Configuration de Serveurs, Virtualisation"),
    ("NFTeam - Support Technique", "Support Technique, Dépannage, Résolution d'Incidents, Maintenance"),
    ("NFTeam - Marketing Numérique", "Marketing en Ligne, Publicité Digitale, Stratégie de Contenu, SEO"),
    ("NFTeam - Qualité Logicielle", "Tests de Logiciels, Assurance Qualité, Test d'Intégration, Test de Performance"),
    ("NFTeam - Analyse de Données", "Analyse de Données, Business Intelligence, Data Mining, Modélisation Statistique"),
    ("NFTeam - Intelligence Artificielle", "Apprentissage Automatique, Traitement du Langage Naturel, Vision par Ordinateur, Robotique"),
    ("NFTeam - Administration Système", "Administration de Systèmes, Gestion de Serveurs, Sécurité des Systèmes, Cloud Computing"),
    ("NFTeam - Innovation Technologique", "Recherche et Développement, Innovation Technologique, Prototypage Rapide, Veille Technologique"),
    ]

    cur.executemany("INSERT OR REPLACE INTO Subgroup (nom_subgroup, types_service) VALUES (?, ?)", subgroup_data)

    conn.commit()
    conn.close()

# Insérer les sous-groupes
#insert_subgroups()

@app.route('/')
def accueil(): 
    if 'user_id' in session:
        user_id = session['user_id']
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id, nom_utilisateur, email FROM Utilisateurs WHERE id = ?", (user_id,))
        utilisateur = cur.fetchone()
        cur.execute("SELECT id, tache, etat, priorite, deadline, types_services FROM TodoList WHERE id_utilisateur = ? ORDER BY priorite DESC, deadline ASC", (user_id,))
        taches = cur.fetchall()
        a_faire = []
        en_cours = []
        finies = []
        today = datetime.now()
        for tache in taches:
            if tache[2] == "A faire":
                a_faire.append(tache)
                if tache[4] is not None:
                    deadline = datetime.strptime(tache[4], "%Y-%m-%d")
            elif tache[2] == "En cours":
                en_cours.append(tache)
            elif tache[2] == "Finie":
                finies.append(tache)
        a_faire = a_faire or []
        en_cours = en_cours or []
        finies = finies or []

        cur.execute("SELECT U.nom_utilisateur FROM OnlineUsers O JOIN Utilisateurs U ON O.user_id = U.id WHERE O.is_online = 1")
        utilisateurs_en_ligne = get_online_users()

        cur.execute("SELECT id, tache, etat, deadline FROM TodoList WHERE id_utilisateur = ?", (user_id,))
        taches_calendrier = cur.fetchall()

        conn.close()

        socketio.emit('update_online_users', utilisateurs_en_ligne, namespace='/')

        return render_template('accueil.html', utilisateur=utilisateur, a_faire=a_faire, en_cours=en_cours, finies=finies, utilisateurs_en_ligne=utilisateurs_en_ligne, user_id=user_id, taches_calendrier=taches_calendrier)
    else:
        return redirect(url_for('connexion'))

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id, nom_utilisateur, email, mot_de_passe FROM Utilisateurs WHERE email = ? and mot_de_passe = ?",
                    (email, mot_de_passe))
        utilisateur = cur.fetchone()

        if utilisateur:
            session['user_id'] = utilisateur[0]

            cur.execute("PRAGMA table_info(OnlineUsers)")
            columns = [row[1] for row in cur.fetchall()]
            if 'last_activity' not in columns:
                cur.execute("ALTER TABLE OnlineUsers ADD COLUMN last_activity DATETIME")

            cur.execute("DELETE FROM OnlineUsers WHERE user_id = ?", (utilisateur[0],))

            cur.execute("INSERT INTO OnlineUsers (user_id, is_online, last_activity) VALUES (?, 1, CURRENT_TIMESTAMP)",
                        (utilisateur[0],))
            print("User record updated in OnlineUsers:", utilisateur[0])

            conn.commit()
            conn.close()

            flash('Connexion réussie', 'success')
            return redirect(url_for('accueil'))
        else:
            flash('Identifiants invalides, veuillez réessayer.', 'danger')

    return render_template('connexion.html')

@app.route('/creer_compte', methods=['GET', 'POST'])
def creer_compte():
    if request.method == 'POST':
        nom_utilisateur = request.form['nom_utilisateur']
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        id_subgroup = request.form['id_subgroup']
        deadline = request.form.get('deadline')
        print("Deadline:", deadline)

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("INSERT INTO Utilisateurs (nom_utilisateur, email, mot_de_passe, id_subgroup) VALUES (?, ?, ?, ?)",
                    (nom_utilisateur, email, mot_de_passe, id_subgroup))
        conn.commit()
        conn.close()
        return redirect(url_for('connexion'))

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT id, nom_subgroup FROM Subgroup")
    subgroups = cur.fetchall()
    conn.close()

    return render_template('creer_compte.html', subgroups=subgroups)

@app.route('/deconnexion')
def deconnexion():
    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO OnlineUsers (user_id, is_online) VALUES (?, 0)", (user_id,))
    cur.execute("DELETE FROM OnlineUsers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    session.pop('user_id', None)    
    return redirect(url_for('accueil'))

@app.route('/ajouter_tache', methods=['POST'])
def ajouter_tache():
    if 'user_id' in session:
        user_id = session['user_id']
        tache = request.form['tache']
        etat = request.form['etat']
        priorite = request.form['priorite']
        deadline = request.form.get('deadline')
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("INSERT INTO TodoList (id_utilisateur, tache, etat, priorite, deadline, types_services) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, tache, etat, priorite, deadline, 0))
        conn.commit()

        return redirect(url_for('accueil'))
    else:
        return


@app.route('/update_task_state', methods=['POST'])
def update_task_state():
    if 'user_id' in session:
        try:
            data = request.get_json()
            task_id = data['task_id']
            new_state = data['new_state']
            user_id = session['user_id']
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("SELECT id FROM TodoList WHERE id = ? AND id_utilisateur = ?", (task_id, user_id))
            task = cur.fetchone()

            if task:
                cur.execute("UPDATE TodoList SET etat = ? WHERE id = ?", (new_state, task_id))
                conn.commit()
                conn.close()
                print("ok")
                return "Mise à jour réussie", 200
            else:
                return "Accès non autorisé à cette tâche", 403
        except Exception as e:
            print(str(e))
            return "Erreur lors de la mise à jour de l'état de la tâche", 500
    else:
        return "Non connecté", 401

def attribuer_commande_automatiquement(sous_groupe_id, description, deadline):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.execute("SELECT id FROM Utilisateurs WHERE id_subgroup = ?", (sous_groupe_id,))
    membres_sous_groupe = cur.fetchall()

    if membres_sous_groupe:
        membres_a_faire_counts = []

        for membre in membres_sous_groupe:
            cur.execute("SELECT COUNT(id) FROM TodoList WHERE id_utilisateur = ? AND etat = 'À faire'", (membre[0],))
            count = cur.fetchone()
            membres_a_faire_counts.append((membre[0], count[0]))

        membres_a_faire_counts.sort(key=lambda x: x[1])

        premier_membre = membres_a_faire_counts[0][0]
        return premier_membre
        # nombre_taches_a_faire = membres_a_faire_counts[0][1]
        # cur.execute("INSERT INTO TodoList (id_utilisateur, tache, deadline) VALUES (?, ?, ?, ?)",
        #             (premier_membre, description, deadline))
        # conn.commit()

    conn.close()

@app.route('/commande', methods=['GET', 'POST'])
def commande():
    if 'user_id' in session:
        user_id = session['user_id']
        utilisateur = session['user_id']
        if request.method == 'POST':
            description = request.form['description']
            deadline = request.form.get('deadline')
            id_subgroup = request.form['id_subgroup']
            types_services = request.form['types_services']
            idofuser = attribuer_commande_automatiquement(id_subgroup, description, deadline)
            if description and id_subgroup:
                conn = sqlite3.connect(DATABASE)
                cur = conn.cursor()
                cur.execute("INSERT INTO TodoList (id_utilisateur, tache, etat, priorite, deadline, types_services) VALUES (?, ?, 'A faire', 1, ?, ?)",(idofuser, description, deadline, types_services))
                conn.commit()
                conn.close()
                flash('Commande créée avec succès.', 'success')
                return redirect(url_for('accueil'))
            else:
                flash('Veuillez remplir tous les champs pour créer une commande.', 'danger')

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id, nom_subgroup FROM Subgroup")
        subgroups = cur.fetchall()
        conn.close()

        return render_template('commande.html', subgroups=subgroups, utilisateur=utilisateur, user_id = user_id)
    else:
        return redirect(url_for('connexion'))

@app.route('/archive_task', methods=['POST'])
def archive_task():
    if 'user_id' in session:
        try:
            data = request.get_json()
            task_id = data['task_id']
            user_id = session['user_id']
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("SELECT id FROM TodoList WHERE id = ? AND id_utilisateur = ?", (task_id, user_id))
            task = cur.fetchone()

            if task:
                cur.execute("DELETE FROM TodoList WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
                print("Tâche archivée et supprimée de la base de données.")
                return "Tâche archivée et supprimée de la base de données", 200
            else:
                return "Accès non autorisé à cette tâche", 403
        except Exception as e:
            print(str(e))
            return "Erreur lors de l'archivage de la tâche", 500
    else:
        return "Non connecté", 401

@app.route('/get_online_users', methods=['GET'])
def get_online_users():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM OnlineUsers WHERE is_online = 1")
    utilisateurs_en_ligne = [row[0] for row in cur.fetchall()]
    conn.close()
    utilisateurs_en_ligne = list(set(utilisateurs_en_ligne))
    socketio.emit('update_online_users', utilisateurs_en_ligne, namespace='/')
    print("Utilisateurs en ligne :", utilisateurs_en_ligne)
    return utilisateurs_en_ligne

@app.route('/get_types_services/<int:subgroup_id>', methods=['GET'])
def get_types_services(subgroup_id):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT types_service FROM Subgroup WHERE id = ?", (subgroup_id,))
    types_services = cur.fetchone()[0].split(', ')
    conn.close()
    options_html = ""
    for service in types_services:
        options_html += f"<option value='{service}'>{service}</option>"

    return options_html

@app.route('/deconnexion_generale', methods=['GET', 'POST'])
def deconnexion_generale():
    if 'user_id' not in session or session['user_id'] != 1:
        flash('Vous n\'avez pas les autorisations nécessaires.', 'error')
        return redirect(url_for('accueil'))

    if request.method == 'POST':
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("UPDATE OnlineUsers SET is_online = 0")
        conn.commit()
        conn.close()
        session.clear()

        flash('Déconnexion générale réussie', 'success')
        return redirect(url_for('accueil'))

    return render_template('connexion.html')

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401

    logged_in_user_id = session['user_id']

    if logged_in_user_id != user_id:
        if logged_in_user_id != 1:
            return jsonify({'error': 'Unauthorized. You can only delete your own account or any account if you are an admin.'}), 403

    if user_id == 1:
        return jsonify({'error': 'Unauthorized. You cannot delete the admin account.'}), 403
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("DELETE FROM TodoList WHERE id_utilisateur = ?", (user_id,))
    cur.execute("DELETE FROM OnlineUsers WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM Utilisateurs WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    session.pop('user_id', None)

    return jsonify({'message': f'User with ID {user_id} and related data has been deleted.'}), 200

@app.route('/editer_profil', methods=['GET', 'POST'])
def editer_profil():
    if 'user_id' in session:
        user_id = session['user_id']

        if request.method == 'POST':
            nouveau_nom_utilisateur = request.form['nouveau_nom_utilisateur']
            nouveau_email = request.form['nouveau_email']
            nouveau_mot_de_passe = request.form['nouveau_mot_de_passe']
            nouveau_id_subgroup = request.form['nouveau_id_subgroup']

            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("UPDATE Utilisateurs SET nom_utilisateur = ?, email = ?, mot_de_passe = ?, id_subgroup = ? WHERE id = ?",
                        (nouveau_nom_utilisateur, nouveau_email, nouveau_mot_de_passe, nouveau_id_subgroup, user_id))
            conn.commit()
            conn.close()

            flash('Profil mis à jour avec succès.', 'success')
            return redirect(url_for('accueil'))

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id, nom_utilisateur, email, id_subgroup FROM Utilisateurs WHERE id = ?", (user_id,))
        utilisateur = cur.fetchone()

        cur.execute("SELECT id, nom_subgroup FROM Subgroup")
        subgroups = cur.fetchall()
        conn.close()

        return render_template('editer_profil.html', utilisateur=utilisateur, subgroups=subgroups, user_id=user_id)

    else:
        return redirect(url_for('connexion'))

@app.route('/supprimer_utilisateurs', methods=['GET', 'POST'])
def supprimer_utilisateurs():
    user_id = session.get('user_id')
    if user_id is None or user_id != 1:
        flash('Vous n\'avez pas les autorisations nécessaires.', 'error')
        return redirect(url_for('accueil'))
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT id, nom_utilisateur, email FROM Utilisateurs WHERE id = ?", (user_id,))
    utilisateur = cur.fetchone()
    conn.commit()
    conn.close()
    if request.method == 'POST':
        utilisateurs_a_supprimer = request.form.getlist('utilisateur_a_supprimer[]')
        print("Utilisateurs à supprimer:", utilisateurs_a_supprimer)
        if utilisateurs_a_supprimer:
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            for utilisateur_id in utilisateurs_a_supprimer:
                if utilisateur_id == "1":
                    return jsonify({'error': 'Not authorized'}), 405
            for utilisateur_id in utilisateurs_a_supprimer:
                cur.execute("DELETE FROM TodoList WHERE id_utilisateur = ?", (utilisateur_id,))
            cur.execute("DELETE FROM OnlineUsers WHERE user_id IN ({})".format(', '.join('?' for _ in utilisateurs_a_supprimer)), utilisateurs_a_supprimer)
            cur.execute("DELETE FROM Utilisateurs WHERE id IN ({})".format(', '.join('?' for _ in utilisateurs_a_supprimer)), utilisateurs_a_supprimer)

            conn.commit()
            conn.close()

            flash('Utilisateurs sélectionnés et leurs tâches supprimés avec succès.', 'success')
            return redirect(url_for('supprimer_utilisateurs'))

        else:
            flash('Aucun utilisateur sélectionné pour la suppression.', 'warning')

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT id, nom_utilisateur, email FROM Utilisateurs")
    utilisateurs = cur.fetchall()
    conn.close()

    return render_template('supprimer_utilisateurs.html', utilisateurs=utilisateurs, utilisateur=utilisateur, user_id=user_id)

@app.route('/update_task_deadline', methods=['POST'])
def update_task_deadline():
    if request.method == 'POST':
        data = request.get_json()
        task_id = data.get('task_id')
        new_deadline = data.get('new_deadline')
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("UPDATE TodoList SET deadline = ? WHERE id = ?", (new_deadline, task_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'})


if __name__ == '__main__':
    #app.run(debug=True)
    #socketio.run(app, host='192.168.1.138', port=80) 
    import threading
    scheduler_thread = threading.Thread(target=schedule_loop)
    scheduler_thread.start()
    socketio.init_app(app)
    app.run(host='127.0.0.1', port=80)
    