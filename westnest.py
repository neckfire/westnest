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
from datetime import datetime



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure secret key
# Configuration de la base de données
DATABASE = 'westnest.db'
socketio = SocketIO(app)  # Ajout de cette ligne


def check_inactive_users():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Set the threshold for inactivity (e.g., 30 minutes)
    threshold = datetime.now() - timedelta(minutes=30)

    # Select users who have not been active since the threshold
    cur.execute("SELECT user_id FROM OnlineUsers WHERE last_activity < ?", (threshold,))
    inactive_users = [row[0] for row in cur.fetchall()]

    # Update the is_online status for inactive users
    cur.executemany("INSERT OR REPLACE INTO OnlineUsers (user_id, is_online) VALUES (?, 0)", [(user_id,) for user_id in inactive_users])
    conn.commit()
    conn.close()

# Schedule the task to run every 5 minutes
schedule.every(5).minutes.do(check_inactive_users)

# Start the scheduling loop in a separate thread
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
    )''')  # Nouvelle table pour suivre les utilisateurs en ligne

    conn.commit()
    conn.close()

create_table()

def insert_subgroups():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Ajouter la société mère (Head)
    cur.execute("INSERT INTO Subgroup (nom_subgroup, types_service) VALUES (?, ?)", ("NFTeam - Head", "Administration, Gestion des Ressources Humaines, Stratégie Marketing, Analyse de Marché, Prise de Décisions Stratégiques, Planification Financière, Communication d'Entreprise, Relations Publiques, Développement Commercial, Supervision des Opérations, Élaboration de Politiques Internes, Recherche de Partenariats, Évaluation des Performances, Gestion de Projet, Élaboration de Budget, Formation du Personnel, Développement Organisationnel, Planification Stratégique."))

    # Ajouter les autres sous-groupes avec des domaines informatiques correspondants
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

        # Récupérer les tâches de l'utilisateur triées par priorité décroissante et date d'échéance
        cur.execute("SELECT id, tache, etat, priorite, deadline, types_services FROM TodoList WHERE id_utilisateur = ? ORDER BY priorite DESC, deadline ASC", (user_id,))
        taches = cur.fetchall()

        # Créez des listes pour chaque état
        a_faire = []
        en_cours = []
        finies = []
        today = datetime.now()
        for tache in taches:
            # Ajoutez la tâche à la liste appropriée en fonction de son état
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

        # Récupérer la liste des utilisateurs en ligne
        cur.execute("SELECT U.nom_utilisateur FROM OnlineUsers O JOIN Utilisateurs U ON O.user_id = U.id WHERE O.is_online = 1")
        utilisateurs_en_ligne = get_online_users()

        conn.close()

        # Émettre un signal pour mettre à jour les utilisateurs en ligne
        socketio.emit('update_online_users', utilisateurs_en_ligne, namespace='/')

        return render_template('accueil.html', utilisateur=utilisateur, a_faire=a_faire, en_cours=en_cours, finies=finies, utilisateurs_en_ligne=utilisateurs_en_ligne, user_id=user_id)
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

            # Update the last_activity timestamp
            cur.execute("PRAGMA table_info(OnlineUsers)")
            columns = [row[1] for row in cur.fetchall()]
            if 'last_activity' not in columns:
                cur.execute("ALTER TABLE OnlineUsers ADD COLUMN last_activity DATETIME")

            # Delete existing records for the user
            cur.execute("DELETE FROM OnlineUsers WHERE user_id = ?", (utilisateur[0],))

            # Insert a new record
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

        # Insérer les données dans la base de données
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("INSERT INTO Utilisateurs (nom_utilisateur, email, mot_de_passe, id_subgroup) VALUES (?, ?, ?, ?)",
                    (nom_utilisateur, email, mot_de_passe, id_subgroup))
        conn.commit()
        conn.close()
        return redirect(url_for('connexion'))

    # Récupérer les sous-groupes depuis la base de données
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
        print("Deadline:", deadline)

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("INSERT INTO TodoList (id_utilisateur, tache, etat, priorite, deadline, types_services) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, tache, etat, priorite, deadline, 0))
        conn.commit()
        conn.close()
    return redirect(url_for('accueil'))

@app.route('/update_task_state', methods=['POST'])
def update_task_state():
    if 'user_id' in session:
        try:
            data = request.get_json()
            task_id = data['task_id']
            new_state = data['new_state']

            # Assurez-vous que l'utilisateur a accès à cette tâche (en fonction de son ID d'utilisateur)
            user_id = session['user_id']
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("SELECT id FROM TodoList WHERE id = ? AND id_utilisateur = ?", (task_id, user_id))
            task = cur.fetchone()

            if task:
                # Mettez à jour l'état de la tâche dans la base de données
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

    # Sélectionnez les utilisateurs du sous-groupe
    cur.execute("SELECT id FROM Utilisateurs WHERE id_subgroup = ?", (sous_groupe_id,))
    membres_sous_groupe = cur.fetchall()

    if membres_sous_groupe:
        # Créez une liste pour suivre le nombre de tâches "A faire" de chaque membre
        membres_a_faire_counts = []

        # Comptez les tâches "A faire" pour chaque membre
        for membre in membres_sous_groupe:
            cur.execute("SELECT COUNT(id) FROM TodoList WHERE id_utilisateur = ? AND etat = 'À faire'", (membre[0],))
            count = cur.fetchone()
            membres_a_faire_counts.append((membre[0], count[0]))

        # Triez les membres en fonction du nombre de tâches "A faire" croissant
        membres_a_faire_counts.sort(key=lambda x: x[1])

        # Attribuez la commande au premier membre de la liste triée
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
                # Créez la commande dans la table TodoList

                conn = sqlite3.connect(DATABASE)
                cur = conn.cursor()
                cur.execute("INSERT INTO TodoList (id_utilisateur, tache, etat, priorite, deadline, types_services) VALUES (?, ?, 'A faire', 1, ?, ?)",(idofuser, description, deadline, types_services))

                conn.commit()
                conn.close()

                flash('Commande créée avec succès.', 'success')
                return redirect(url_for('accueil'))
            else:
                flash('Veuillez remplir tous les champs pour créer une commande.', 'danger')

        # Récupérez la liste des sous-groupes
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
            
            # Assurez-vous que l'utilisateur a accès à cette tâche (en fonction de son ID d'utilisateur)
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("SELECT id FROM TodoList WHERE id = ? AND id_utilisateur = ?", (task_id, user_id))
            task = cur.fetchone()

            if task:
                # Supprimez la tâche de la base de données
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

# Ajoutez cette route dans votre application Flask
@app.route('/get_types_services/<int:subgroup_id>', methods=['GET'])
def get_types_services(subgroup_id):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT types_service FROM Subgroup WHERE id = ?", (subgroup_id,))
    types_services = cur.fetchone()[0].split(', ')
    conn.close()

    # Générez les balises d'option HTML pour les types de services
    options_html = ""
    for service in types_services:
        options_html += f"<option value='{service}'>{service}</option>"

    return options_html

@app.route('/deconnexion_generale', methods=['GET', 'POST'])
def deconnexion_generale():
    # Vérifier si l'utilisateur connecté a un ID égal à 1
    if 'user_id' not in session or session['user_id'] != 1:
        flash('Vous n\'avez pas les autorisations nécessaires.', 'error')
        return redirect(url_for('accueil'))

    if request.method == 'POST':
        # Déconnecter tous les utilisateurs
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("UPDATE OnlineUsers SET is_online = 0")
        conn.commit()
        conn.close()

        # Vider toutes les sessions
        session.clear()

        flash('Déconnexion générale réussie', 'success')
        return redirect(url_for('accueil'))

    return render_template('connexion.html')

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401

    logged_in_user_id = session['user_id']

    # Check if the logged-in user is the same as the user being deleted
    if logged_in_user_id != user_id:
        # Check if the logged-in user is an admin (ID=1)
        if logged_in_user_id != 1:
            return jsonify({'error': 'Unauthorized. You can only delete your own account or any account if you are an admin.'}), 403

    # Check if the user being deleted is not the admin (ID=1)
    if user_id == 1:
        return jsonify({'error': 'Unauthorized. You cannot delete the admin account.'}), 403

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Delete user-related data from TodoList table
    cur.execute("DELETE FROM TodoList WHERE id_utilisateur = ?", (user_id,))

    # Delete user-related data from OnlineUsers table
    cur.execute("DELETE FROM OnlineUsers WHERE user_id = ?", (user_id,))

    # Delete user-related data from d'autres_tables, à adapter selon la structure exacte de votre base de données

    # Delete the user
    cur.execute("DELETE FROM Utilisateurs WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    # Clear the session after deleting the user
    session.pop('user_id', None)

    return jsonify({'message': f'User with ID {user_id} and related data has been deleted.'}), 200

@app.route('/editer_profil', methods=['GET', 'POST'])
def editer_profil():
    if 'user_id' in session:
        user_id = session['user_id']

        if request.method == 'POST':
            # Récupérez les données du formulaire
            nouveau_nom_utilisateur = request.form['nouveau_nom_utilisateur']
            nouveau_email = request.form['nouveau_email']
            nouveau_mot_de_passe = request.form['nouveau_mot_de_passe']
            nouveau_id_subgroup = request.form['nouveau_id_subgroup']

            # Mettez à jour les informations du profil dans la base de données
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            cur.execute("UPDATE Utilisateurs SET nom_utilisateur = ?, email = ?, mot_de_passe = ?, id_subgroup = ? WHERE id = ?",
                        (nouveau_nom_utilisateur, nouveau_email, nouveau_mot_de_passe, nouveau_id_subgroup, user_id))
            conn.commit()
            conn.close()

            flash('Profil mis à jour avec succès.', 'success')
            return redirect(url_for('accueil'))

        # Récupérez les informations actuelles du profil
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT id, nom_utilisateur, email, id_subgroup FROM Utilisateurs WHERE id = ?", (user_id,))
        utilisateur = cur.fetchone()

        # Récupérez la liste des sous-groupes pour le formulaire
        cur.execute("SELECT id, nom_subgroup FROM Subgroup")
        subgroups = cur.fetchall()
        conn.close()

        return render_template('editer_profil.html', utilisateur=utilisateur, subgroups=subgroups, user_id=user_id)

    else:
        return redirect(url_for('connexion'))

# Ajouter cette route dans votre application Flask
@app.route('/supprimer_utilisateurs', methods=['GET', 'POST'])
def supprimer_utilisateurs():
    # Vérifier si l'utilisateur connecté a un ID égal à 1 (admin)
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
        # Récupérer la liste des utilisateurs sélectionnés à supprimer
        utilisateurs_a_supprimer = request.form.getlist('utilisateur_a_supprimer[]')
        print("Utilisateurs à supprimer:", utilisateurs_a_supprimer)
        # Vérifier s'il y a des utilisateurs à supprimer
        if utilisateurs_a_supprimer:
            conn = sqlite3.connect(DATABASE)
            cur = conn.cursor()
            for utilisateur_id in utilisateurs_a_supprimer:
                if utilisateur_id == "1":
                    return jsonify({'error': 'Not authorized'}), 405
            # Supprimer les tâches des utilisateurs sélectionnés
            for utilisateur_id in utilisateurs_a_supprimer:
                cur.execute("DELETE FROM TodoList WHERE id_utilisateur = ?", (utilisateur_id,))

            # Supprimer les lignes correspondantes dans la table OnlineUsers
            cur.execute("DELETE FROM OnlineUsers WHERE user_id IN ({})".format(', '.join('?' for _ in utilisateurs_a_supprimer)), utilisateurs_a_supprimer)

            # Supprimer les utilisateurs sélectionnés
            cur.execute("DELETE FROM Utilisateurs WHERE id IN ({})".format(', '.join('?' for _ in utilisateurs_a_supprimer)), utilisateurs_a_supprimer)

            conn.commit()
            conn.close()

            flash('Utilisateurs sélectionnés et leurs tâches supprimés avec succès.', 'success')
            return redirect(url_for('supprimer_utilisateurs'))

        else:
            flash('Aucun utilisateur sélectionné pour la suppression.', 'warning')

    # Récupérer la liste des utilisateurs pour l'affichage
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT id, nom_utilisateur, email FROM Utilisateurs")
    utilisateurs = cur.fetchall()
    conn.close()

    return render_template('supprimer_utilisateurs.html', utilisateurs=utilisateurs, utilisateur=utilisateur, user_id=user_id)


if __name__ == '__main__':
    #app.run(debug=True)
    #socketio.run(app, host='192.168.1.138', port=80) 
    import threading
    scheduler_thread = threading.Thread(target=schedule_loop)
    scheduler_thread.start()
    socketio.init_app(app)
    app.run(host='0.0.0.0', port=80)
    
    
