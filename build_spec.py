from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
from pathlib import Path

OUT = Path(r"C:\Users\f5jwf\Documents\SDR_Bridge\SDR_Bridge_Specification_v1.1.docx")
BLUE = "1F4E78"; LIGHT = "D9EAF7"; PALE = "EEF5FA"; DARK = "17324D"; GRAY = "59636E"; RED = "9C2F2F"

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)
def margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc.get_or_add_tcPr(); tcMar = tc.first_child_found_in('w:tcMar')
    if tcMar is None: tcMar=OxmlElement('w:tcMar'); tc.append(tcMar)
    for tag,val in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        n=OxmlElement('w:'+tag); n.set(qn('w:w'),str(val)); n.set(qn('w:type'),'dxa'); tcMar.append(n)
def set_repeat(row):
    trPr=row._tr.get_or_add_trPr(); e=OxmlElement('w:tblHeader'); e.set(qn('w:val'),'true'); trPr.append(e)
def set_cell_text(cell, text, bold=False, color=None, size=9):
    cell.text=''; p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(0)
    r=p.add_run(text); r.bold=bold; r.font.size=Pt(size); r.font.name='Aptos'; r._element.get_or_add_rPr().rFonts.set(qn('w:ascii'),'Aptos')
    if color: r.font.color.rgb=RGBColor.from_string(color)
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; margins(cell)
def table(headers, rows, widths=None):
    t=doc.add_table(rows=1, cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    for i,h in enumerate(headers):
        set_cell_text(t.rows[0].cells[i],h,True,'FFFFFF',9); shade(t.rows[0].cells[i],BLUE)
    set_repeat(t.rows[0])
    for ridx,row in enumerate(rows):
        cells=t.add_row().cells
        for i,v in enumerate(row):
            set_cell_text(cells[i],str(v),False,None,8.5)
            if ridx%2: shade(cells[i],'F5F8FA')
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(2)
    return t
def para(text='', style=None, bold_lead=None):
    p=doc.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold=True; p.add_run(text[len(bold_lead):])
    else: p.add_run(text)
    return p
def bullets(items):
    for x in items: para(x,'List Bullet')
def req(id_, title, text, priority='Must'):
    p=doc.add_paragraph(style='Requirement'); p.add_run(f'{id_} — {title}. ').bold=True; p.add_run(text); p.add_run(f' [{priority}]').italic=True

doc=Document(); sec=doc.sections[0]
sec.page_width=Inches(8.5); sec.page_height=Inches(11); sec.top_margin=Inches(.8); sec.bottom_margin=Inches(.75); sec.left_margin=Inches(.85); sec.right_margin=Inches(.85); sec.header_distance=Inches(.35); sec.footer_distance=Inches(.35)
styles=doc.styles
normal=styles['Normal']; normal.font.name='Aptos'; normal.font.size=Pt(10); normal.font.color.rgb=RGBColor.from_string('20262D'); normal.paragraph_format.space_after=Pt(4.5); normal.paragraph_format.line_spacing=1.06
for name,size,before,after in [('Title',28,0,10),('Heading 1',17,16,7),('Heading 2',13,12,5),('Heading 3',11,9,4)]:
    s=styles[name]; s.font.name='Aptos Display' if name!='Normal' else 'Aptos'; s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor.from_string(BLUE); s.paragraph_format.space_before=Pt(before); s.paragraph_format.space_after=Pt(after); s.paragraph_format.keep_with_next=True
styles['List Bullet'].paragraph_format.left_indent=Inches(.35); styles['List Bullet'].paragraph_format.first_line_indent=Inches(-.18); styles['List Bullet'].paragraph_format.space_after=Pt(3)
styles.add_style('Requirement',WD_STYLE_TYPE.PARAGRAPH); rs=styles['Requirement']; rs.font.name='Aptos'; rs.font.size=Pt(9.2); rs.paragraph_format.left_indent=Inches(.15); rs.paragraph_format.right_indent=Inches(.1); rs.paragraph_format.space_after=Pt(4)

# Header/footer
h=sec.header.paragraphs[0]; h.text='SPÉCIFICATION SYSTÈME  |  PASSERELLE SDR MULTI-CLIENT'; h.style=styles['Normal']; h.runs[0].font.size=Pt(8); h.runs[0].font.bold=True; h.runs[0].font.color.rgb=RGBColor.from_string(GRAY)
f=sec.footer.paragraphs[0]; f.alignment=WD_ALIGN_PARAGRAPH.RIGHT; f.add_run('Version 1.1 — 9 août 2026  |  ')
fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); f._p.append(fld)
for r in f.runs: r.font.size=Pt(8); r.font.color.rgb=RGBColor.from_string(GRAY)

# Cover
p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(70); p.add_run('SPÉCIFICATION LOGICIELLE').bold=True; p.runs[0].font.size=Pt(11); p.runs[0].font.color.rgb=RGBColor.from_string(BLUE)
p=doc.add_paragraph(style='Title'); p.add_run('SDR_Bridge\nPasserelle SDR I/Q multi-client')
p=doc.add_paragraph(); p.add_run('Acquisition USB d’un SDRplay RSP1A, partage local entre applications Windows et extension future UDP/LAN').italic=True; p.runs[0].font.size=Pt(14); p.runs[0].font.color.rgb=RGBColor.from_string(GRAY)
doc.add_paragraph('\n')
n=doc.add_table(rows=4,cols=2); n.autofit=False
for i,(a,b) in enumerate([('Statut','Spécification de référence'),('Version','1.1'),('Date','9 août 2026'),('Cible','Windows 10/11 x64; exécution locale')]):
    set_cell_text(n.cell(i,0),a,True,BLUE,9); set_cell_text(n.cell(i,1),b,False,None,9); shade(n.cell(i,0),PALE)
doc.add_paragraph('\n')
p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.2); p.paragraph_format.right_indent=Inches(.2); p.add_run('Décision d’architecture recommandée\n').bold=True; p.add_run('C++20 pour le chemin de données et les couches système; Python uniquement pour prototypage, automatisation ou GUI non critique. PlatformIO n’est pas la cible adaptée à une application/driver de bureau.')
p._p.get_or_add_pPr().append(OxmlElement('w:shd')); p._p.pPr[-1].set(qn('w:fill'),LIGHT)
doc.add_page_break()

para('1. Objet et périmètre','Heading 1')
para("Le produit est une passerelle logicielle installée sur une machine hôte reliée en USB à un récepteur SDR. Elle acquiert un flux d’échantillons complexes I/Q, centralise le pilotage du récepteur, puis distribue ce même flux à trois ou quatre postes clients simultanés. Une interface graphique permet la supervision du signal et des sessions.")
para("Hypothèse matérielle : la référence « SDRPLAY RF1A » est interprétée comme SDRplay RSP1A. L’accès matériel doit passer par l’API/SDK et le pilote officiellement fournis par SDRplay, sous réserve de leurs conditions de redistribution.")
para('1.1 Objectifs','Heading 2'); bullets([
    'Acquérir de façon continue les données I/Q avec une bande utile cible de 2 MHz.',
    'Permettre le réglage de la fréquence, du gain et des paramètres exposés par le matériel.',
    'Distribuer un flux cohérent à 3 applications clientes garanties et 4 en objectif, exécutées sur le même PC Windows que le serveur.',
    'Faire fonctionner HDSDR, ANTRACK, WSJT-X et QMAP sans modifier leur exécutable; l’installation ou la configuration d’un adaptateur standard reste autorisée.',
    'Afficher spectre, waterfall, état radio, débit, pertes et clients connectés.',
])
para('1.2 Hors périmètre initial','Heading 2'); bullets([
    'Émission RF, diversité multi-récepteurs, synchronisation GPSDO et traitement démodulation métier.',
    'Accès concurrent avec des fréquences ou taux d’échantillonnage différents sur un SDR mono-tuner.',
    'Garantie de compatibilité universelle hors de la matrice HDSDR, ANTRACK, WSJT-X, QMAP et des versions explicitement certifiées.',
])

para('2. Point d’architecture critique : “faire croire à une connexion USB”','Heading 1')
para("Un périphérique USB physique ne peut pas être attaché simultanément à plusieurs machines. La compatibilité transparente nécessite donc une couche côté client. Deux modes sont spécifiés :")
table(['Mode','Principe','Compatibilité','Priorité'],[
 ['A — Adaptateur local','Une DLL/plugin ou source virtuelle expose l’interface attendue et lit le flux via IPC local.','Cible HDSDR, ANTRACK, WSJT-X et QMAP selon leur interface d’entrée réelle.','MVP'],
 ['B — Périphérique USB virtuel','Un driver/bus USB virtuel présente un périphérique au système client et transporte contrôle + flux via IP.','Potentiellement maximale, mais forte complexité, signature de pilote et validation par OS.','Phase 2 / étude'],
 ['C — UDP/LAN futur','Un protocole I/Q documenté diffuse sur le LAN, inspiré des architectures WSJT-X/QMAP/Linrad.','Extension réseau; profils d’interopérabilité à valider par application.','Phase future'],
], [1.25,2.65,2.2,.75])
para("Recommandation : utiliser en priorité un bus I/Q local partagé (mémoire partagée + canal de contrôle) et des adaptateurs propres à chaque famille d’application. Pour HDSDR, un module ExtIO est la piste prioritaire. Pour WSJT-X, QMAP et ANTRACK, une étude d’interface doit déterminer si l’entrée attendue est I/Q, audio, UDP ou issue d’un moteur de décodage. L’émulation USB générique reste un lot séparé et ne doit pas être considérée comme acquise.")

para('3. Utilisateurs et cas d’usage','Heading 1')
table(['Acteur','Besoin principal','Droits'],[
 ['Module serveur / GUI','Configure le SDR et surveille la réception.','Contrôle exclusif de tous les réglages.'],['Application cliente','Consomme le flux ou la représentation attendue.','Lecture seule; aucune commande SDR.'],['Administrateur Windows','Installe, met à jour et diagnostique.','Administration locale.'],['Adaptateur client','Présente une source compatible à l’application.','Lecture seule.']], [1.35,2.65,2.4])
para('Cas nominal','Heading 2'); bullets([
 'Le serveur détecte le RSP1A, charge son API et démarre une session à 2 MS/s.',
 'L’opérateur règle fréquence centrale, gain et tous les autres paramètres exclusivement dans la GUI du serveur.',
 'Trois ou quatre applications du même PC reçoivent les mêmes blocs I/Q horodatés, dans l’ordre.',
 'Un client lent ne bloque jamais l’acquisition ni les autres clients; ses pertes sont comptabilisées.',
])

para('4. Exigences fonctionnelles','Heading 1')
para('4.1 Acquisition et contrôle du SDR','Heading 2')
req('FR-SDR-001','Détection','Détecter, identifier et ouvrir le SDR connecté en USB; afficher numéro de série, modèle, état et version d’API.')
req('FR-SDR-002','Acquisition I/Q','Acquérir un flux complexe continu à un taux configurable couvrant au minimum une bande utile de 2 MHz, sans conversion inutile dans le chemin critique.')
req('FR-SDR-003','Paramètres','Exposer fréquence centrale, taux d’échantillonnage, largeur de bande, gain/LNA/IF, AGC, correction DC/IQ et sélection d’antenne lorsqu’ils sont supportés.')
req('FR-SDR-004','Application atomique','Valider les plages, sérialiser les commandes et notifier tous les clients de chaque changement effectif.')
req('FR-SDR-005','Reconnexion','Détecter une déconnexion USB, arrêter proprement le flux, tenter une reconnexion configurable et conserver la dernière configuration valide.')
req('FR-SDR-006','Autorité unique','Tous les réglages du SDR sont définis dans le module serveur. Les applications clientes sont en lecture seule et leurs demandes de réglage éventuelles sont refusées ou neutralisées de manière compatible.')
para('4.2 Distribution multi-client','Heading 2')
req('FR-NET-001','Capacité locale','Supporter 3 applications clientes simultanées en exigence minimale et 4 en objectif, sur le même poste Windows 10/11 que le serveur.')
req('FR-NET-002','Données','Distribuer des blocs I/Q avec numéro de séquence, horodatage monotone, format, taux et identifiant de configuration.')
req('FR-NET-003','Isolement','Allouer une file bornée par client. En cas de retard, supprimer les blocs les plus anciens du client concerné et incrémenter son compteur de pertes.')
req('FR-NET-004','IPC local','Pour le MVP, séparer contrôle et données via IPC Windows local : mémoire partagée/ring buffer pour I/Q et named pipe ou socket loopback pour signalisation et métadonnées.')
req('FR-NET-005','Lecture seule','Aucune application cliente ne peut acquérir un verrou de contrôle ou modifier le matériel; seule la GUI/service serveur possède cette autorité.')
req('FR-NET-006','Extension UDP/LAN','Prévoir une interface modulaire future de diffusion I/Q par UDP sur le LAN, avec séquences, timestamps, description de format et statistiques de pertes.','Should')
para('4.3 Compatibilité client','Heading 2')
req('FR-CMP-001','Adaptateur','Fournir un composant installé côté client exposant l’interface attendue par le logiciel cible et consommant le protocole réseau du serveur.')
req('FR-CMP-002','Transparence','Reproduire les appels d’ouverture, configuration, démarrage, callbacks I/Q, arrêt et fermeture nécessaires à la matrice de logiciels certifiés.')
req('FR-CMP-003','Versions','Maintenir une matrice explicite OS / architecture / version d’API / logiciel. Toute combinaison hors matrice est non garantie.')
req('FR-CMP-004','USB virtuel','Soumettre l’option driver USB virtuel à une preuve de concept séparée incluant signature, Plug-and-Play, alimentation, reset, timeouts et désinstallation sûre.','Should')
req('FR-CMP-005','Applications obligatoires','Certifier HDSDR, ANTRACK, WSJT-X et QMAP sans modification de leurs exécutables. Une DLL/plugin officiellement chargeable, un périphérique audio virtuel ou une configuration d’entrée existante est acceptable.')
req('FR-CMP-006','Versions','La conception détaillée doit relever les versions 32/64 bits installées et figer au moins une version Windows 10 et une version Windows 11 de chaque application cible.')
para('4.4 Interface graphique','Heading 2')
req('FR-GUI-001','Vue radio','Afficher modèle, série, fréquence, gain, taux, largeur de bande, état USB et commandes autorisées.')
req('FR-GUI-002','Visualisation','Afficher puissance temporelle, spectre FFT et waterfall, avec cadence d’affichage réglable et sans ralentir le chemin de données.')
req('FR-GUI-003','Clients','Afficher nom/adresse, mode, durée, débit, latence estimée, dernière séquence et pertes de chaque client.')
req('FR-GUI-004','Alertes','Signaler surcharge CPU, tampon proche du seuil, pertes, déconnexion SDR et échec d’authentification.')

para('4.5 Installation et exécution Windows','Heading 2')
req('FR-INS-001','Exécutable','Le module doit être fourni comme application Windows x64 directement exécutable (.exe), sans environnement Python ni outil de développement requis sur le poste cible.')
req('FR-INS-002','Installation','Fournir un setup.exe signé installant le serveur, la GUI, les runtimes, les adaptateurs 32/64 bits nécessaires et les raccourcis; prévoir une désinstallation propre.')
req('FR-INS-003','Démarrage','Permettre un lancement interactif et, en option, un démarrage automatique à l’ouverture de session. L’installation d’un service Windows ne sera retenue que si elle est nécessaire pour les adaptateurs.')

para('4.6 Matrice de compatibilité minimale','Heading 2')
table(['Application','Compatibilité sans modification','Adaptateur envisagé','Validation requise'],[
 ['HDSDR','Obligatoire','DLL ExtIO 32/64 bits consommant le bus I/Q local.','Ouverture, réception, fermeture; commandes SDR ignorées ou reflétées depuis le serveur.'],
 ['ANTRACK','Obligatoire','À déterminer après identification de l’interface d’entrée exacte.','Nom produit, version, architecture et mécanisme d’entrée à relever.'],
 ['WSJT-X','Obligatoire','Périphérique audio virtuel ou interface réseau supportée; I/Q brut seulement si réellement accepté.','Réception/décodage sans patch de l’application.'],
 ['QMAP','Obligatoire','Interface locale ou UDP compatible avec le mode d’entrée documenté.','Réception et traitement sans patch de l’application.'],
 ['Linrad','Référence future LAN','Profil UDP à étudier comme référence d’interopérabilité.','PoC de diffusion LAN.']], [1.05,1.55,2.3,1.85])

para('5. Architecture logique proposée','Heading 1')
para('Chaîne de traitement','Heading 2')
para('RSP1A + pilote constructeur  →  Adaptateur matériel  →  Pool de blocs I/Q  →  Fan-out zéro/minimum copie  →  files client  →  transport réseau  →  adaptateur client  →  logiciel SDR')
table(['Composant','Responsabilité','Technologie recommandée'],[
 ['Hardware Adapter','Encapsule l’API SDRplay, callbacks, paramètres et erreurs.','C++20, SDK constructeur'],['Stream Core','Pool mémoire, séquences, timestamps, fan-out, backpressure.','C++20, threads dédiés'],['Control Service','Configuration exclusive serveur, sessions et statistiques.','Protocole binaire local versionné'],['Local Transport','Ring buffer partagé, signalisation et métadonnées.','Shared memory + named pipes Windows'],['Client Adapter','Expose ExtIO, audio virtuel, API/plugin ou autre entrée supportée.','C/C++ selon ABI 32/64 bits'],['LAN Transport (futur)','Paquets I/Q UDP, pacing, séquences et statistiques.','UDP versionné; profils QMAP/Linrad à étudier'],['GUI','Supervision, FFT décimée, clients, journaux.','Qt 6 / QML; PySide6 possible hors chemin critique']], [1.35,3.0,2.65])
para('Modèle de concurrence','Heading 2'); bullets([
 'Thread/callback acquisition : copie dans un pool préalloué et retour immédiat au SDK.',
 'Thread fan-out : référence le bloc pour chaque client sans recopier le payload lorsque possible.',
 'Un worker d’émission par client ou boucle I/O asynchrone; aucune attente réseau dans le callback SDR.',
 'Thread GUI/FFT séparé consommant un flux décimé ou des blocs échantillonnés.',
])

para('6. Protocole et modèle de données','Heading 1')
para('Le contrat de données est identique entre le bus local et la future diffusion LAN. Le transport local est prioritaire et ne paie pas le coût réseau. Le transport UDP sera ajouté comme backend optionnel, limité au LAN, sans dépendance obligatoire à un protocole propriétaire.')
table(['Champ paquet I/Q','Type indicatif','Description'],[
 ['magic/version','u32/u16','Identification et évolution du protocole.'],['session_id','u64','Session d’acquisition.'],['sequence','u64','Numéro de bloc monotone.'],['timestamp_ns','u64','Temps monotone du premier échantillon.'],['config_revision','u32','Révision des réglages actifs.'],['sample_format','u8','Ex. S16LE IQ entrelacé ou F32LE.'],['sample_count','u32','Nombre de paires I/Q.'],['payload_crc','u32','Optionnel sur UDP.'],['payload','bytes','Échantillons I/Q.']], [1.55,1.3,4.15])
para('Le protocole de contrôle doit être versionné, extensible, little-endian si binaire, et fournir : Hello/Capabilities, Open/Close, Acquire/ReleaseControl, SetConfig, Start/Stop, SubscribeStats, KeepAlive et Error. Les changements de configuration créent une nouvelle config_revision et une discontinuité explicitement signalée.')
para('Choix I/Q de référence','Heading 2')
para('Le format de référence retenu est I16/Q16 signé, little-endian et entrelacé (S16LE IQ), à 2,000 MS/s complexes pour la configuration initiale. Ce choix limite le débit à 8 MB/s par consommateur et évite une conversion flottante systématique. L’adaptateur matériel conserve autant que possible le format natif livré par le SDK; une métadonnée décrit l’échelle utile. F32 reste disponible uniquement pour les adaptateurs qui l’exigent. Le lot P0 doit confirmer la plage, l’échelle et le taux réellement acceptés par la version du SDK/RSP1A.')

para('7. Dimensionnement et performances','Heading 1')
para('Pour 2 MS/s complexes, le débit utile dépend du format :')
table(['Format','Calcul','Par client','4 clients (hors overhead)'],[
 ['I16 + Q16','2 000 000 × 4 octets','8 MB/s ≈ 64 Mbit/s','32 MB/s ≈ 256 Mbit/s'],['F32 + F32','2 000 000 × 8 octets','16 MB/s ≈ 128 Mbit/s','64 MB/s ≈ 512 Mbit/s'],['I8 + Q8','2 000 000 × 2 octets','4 MB/s ≈ 32 Mbit/s','16 MB/s ≈ 128 Mbit/s']], [1.25,2.0,1.65,2.1])
para('Pour le fonctionnement local obligatoire, la mémoire partagée évite de multiplier ce débit sur l’interface réseau. Pour l’option future LAN, Ethernet 1 Gbit/s câblé est recommandé, le format I16 est privilégié et le Wi-Fi n’est pas garanti. Le profil UDP ajoute numéros de séquence et télémétrie mais aucune retransmission temps réel par défaut; prévoir 25 % de marge.')
table(['Indicateur','Cible MVP','Méthode'],[
 ['Continuité acquisition','≥ 8 h sans arrêt imputable au produit','Soak test'],['Pertes serveur à 2 MS/s / 4 clients','0 bloc dans le LAN de référence','Compteurs séquence'],['Latence bout-en-bout','≤ 100 ms, objectif ≤ 50 ms','Timestamp injecté/mesuré'],['CPU serveur','≤ 60 % sur machine de référence','Profilage'],['Mémoire','Stable; aucune croissance sur 8 h','Monitoring RSS/heap'],['Reconfiguration','≤ 500 ms hors contrainte matériel','Mesure commande → premier bloc']], [2.1,2.2,2.6])

para('8. Exigences non fonctionnelles','Heading 1')
req('NFR-PERF-001','Temps réel souple','Éviter allocation, verrou long et journalisation synchrone dans le callback d’acquisition.')
req('NFR-REL-001','Résilience','Une panne ou déconnexion client ne doit pas arrêter le SDR ni les autres sessions.')
req('NFR-SEC-001','Authentification','Exiger un jeton ou certificat; prévoir rôles administrateur, opérateur et observateur.')
req('NFR-SEC-002','Chiffrement','Supporter TLS 1.3 pour le contrôle et DTLS/QUIC/TLS selon le transport des données; autoriser un mode LAN de laboratoire explicitement signalé.')
req('NFR-OBS-001','Observabilité','Journaliser événements et erreurs avec rotation; exposer débit, files, pertes, latence, CPU et état SDR.')
req('NFR-MNT-001','Maintenabilité','Séparer SDK matériel, cœur de flux, transport, GUI et adaptateurs clients via interfaces testables.')
req('NFR-CMP-001','Portabilité','Serveur Windows 10/11 x64 prioritaire. Linux peut être ajouté si le SDK matériel et les logiciels cibles le permettent.')
req('NFR-DEP-001','Déploiement autonome','Le setup embarque toutes les dépendances redistribuables. Après installation, le module démarre depuis le menu Démarrer ou un raccourci bureau sans environnement de développement.')

para('9. Choix technologiques','Heading 1')
table(['Option','Forces','Limites','Décision'],[
 ['Python','Prototype rapide, PySide6, asyncio, NumPy FFT.','GIL, copies, callbacks natifs et packaging/driver; risque sur jitter.','GUI/outils/prototype'],['C++20','Contrôle mémoire/threads, ABI native, plugins et drivers, débit prévisible.','Développement plus exigeant.','Cœur recommandé'],['PlatformIO','Excellent pour firmware embarqué.','Pas adapté au SDK/driver/app desktop Windows.','Non retenu pour le serveur'],['Rust','Sécurité mémoire et performance.','Interop SDK/driver et compétences à valider.','Alternative future']], [1.1,2.15,2.35,1.25])
para('Architecture recommandée : service C++20 (CMake + vcpkg/Conan), Qt 6/QML pour l’interface, Protobuf pour les contrats, tests Catch2/GoogleTest. Une GUI PySide6 est acceptable si la FFT est décimée et le flux brut reste dans la bibliothèque C++.')

para('10. Sécurité et exploitation','Heading 1'); bullets([
 'Écoute réseau limitée aux interfaces configurées; pare-feu documenté; aucun port ouvert par défaut sur réseau public.',
 'Secrets hors fichiers journaux; stockage protégé par l’OS; révocation des jetons.',
 'Installation signée. Pour tout driver Windows : signature appropriée, package INF, restauration et désinstallation testées.',
 'Mise à jour compatible avec le protocole N-1 lorsque possible; export d’un bundle de diagnostic sans données I/Q par défaut.',
 'Respect des licences SDRplay/SDK et interdiction de redistribuer ou imiter des composants propriétaires sans autorisation.',
])

para('11. Gestion des erreurs','Heading 1')
table(['Événement','Comportement requis'],[
 ['SDR absent au démarrage','GUI disponible; état “attente matériel”; nouvelle détection périodique.'],['Déconnexion USB','Stopper le flux, notifier les clients, vider les files, tenter reconnexion.'],['Client trop lent','Drop local contrôlé; compteur et alerte; aucune pression sur acquisition.'],['Perte réseau','Détecter par keepalive; fermer la session et libérer les ressources.'],['Commande invalide','Refuser sans modifier la configuration; retourner code, champ et plage valide.'],['Échec partiel de réglage','Restaurer l’état précédent si possible ou publier l’état réellement lu du matériel.']], [2.0,4.5])

para('12. Tests et critères d’acceptation','Heading 1')
table(['ID','Scénario','Critère'],[
 ['AT-01','Acquisition S16LE à 2 MS/s pendant 8 h','Aucun crash/fuite; compteurs conformes.'],['AT-02','Quatre applications locales simultanées','Chaque adaptateur reçoit des séquences cohérentes; aucune perte serveur.'],['AT-03','Application volontairement ralentie','Seule cette application perd des blocs; acquisition et autres clients restent stables.'],['AT-04','Changement fréquence/gain dans le serveur','Tous les clients observent la nouvelle révision; aucune application ne pilote le SDR.'],['AT-05','Débranchement/rebranchement USB','Erreur visible, sessions notifiées, récupération sans redémarrage si supportée.'],['AT-06','HDSDR, ANTRACK, WSJT-X et QMAP','Chaque version certifiée démarre et reçoit sans modification de son exécutable.'],['AT-07','Installation Windows 10/11','setup.exe installe, lance et désinstalle le produit sur machine propre.'],['AT-08','Charge GUI','Waterfall actif sans pertes supplémentaires ni dépassement CPU cible.'],['AT-09','UDP/LAN futur','Quatre destinataires LAN reçoivent le profil I16 documenté avec pertes mesurables.']], [.65,2.8,3.05])

para('13. Lots de réalisation','Heading 1')
table(['Lot','Contenu','Sortie'],[
 ['P0 — Faisabilité','Valider SDK RSP1A, S16LE/2 MS/s, callbacks, licences et interfaces des applications.','Capture + matrice d’entrée'],['P1 — Cœur local','Service C++, bus mémoire partagé, fan-out 4 processus et client de test.','Flux local stable 8 h'],['P2 — GUI','Réglages exclusifs serveur, FFT/waterfall, état et clients.','Application opérateur'],['P3 — Compatibilité','Adaptateurs HDSDR, ANTRACK, WSJT-X et QMAP 32/64 bits selon besoin.','Matrice logiciels certifiée'],['P4 — UDP/LAN futur','Backend UDP et profils QMAP/Linrad/WSJT-X pertinents.','PoC LAN documenté'],['P5 — USB virtuel (option)','PoC driver/bus virtuel et certification.','Décision go/no-go'],['P6 — Industrialisation','EXE, setup signé, désinstallation, sécurité, logs, CI/CD et documentation.','Release candidate']], [1.35,3.65,1.5])

para('14. Risques et points ouverts','Heading 1')
table(['Risque / décision','Impact','Traitement'],[
 ['Licence et ABI SDRplay','Peut bloquer le proxy transparent.','Obtenir accord et versions SDK autorisées avant P3.'],['Versions exactes non figées','Impossible de garantir toutes les variantes 32/64 bits.','Inventorier les versions installées sur les PC cibles.'],['Émulation USB virtuelle','Coût, signature et maintenance élevés.','PoC isolé; privilégier adaptateur API/plugin.'],['Entrées hétérogènes','Toutes les applications ne consomment pas nécessairement de l’I/Q brut.','Créer l’adaptateur correspondant à l’entrée officiellement supportée.'],['Réseau futur insuffisant','Pertes à 4 clients LAN, surtout F32/Wi-Fi.','I16, Ethernet 1 Gb/s, files bornées, télémétrie.'],['Échelle/taux SDK à confirmer','Le SDK peut imposer format, plage ou taux.','Valider S16LE à 2 MS/s et documenter toute conversion dans P0.']], [2.2,1.45,2.85])
para('Décisions acquises et données restant à relever','Heading 2'); bullets([
 'Applications obligatoires : HDSDR, ANTRACK, WSJT-X et QMAP, sans modification de leur exécutable.',
 'Topologie obligatoire : serveur et trois ou quatre applications sur le même PC Windows 10 ou 11.',
 'Autorité : tous les paramètres SDR sont configurés uniquement au niveau du module serveur.',
 'Format de référence : S16LE IQ à 2,000 MS/s; validation finale contre le SDK lors du lot P0.',
 'Réseau : LAN uniquement; diffusion UDP reportée à une option future inspirée des mécanismes QMAP/Linrad/WSJT-X pertinents.',
 'À relever : versions exactes, architecture 32/64 bits et interface d’entrée réellement utilisée par chaque application.',
])

para('15. Définition de terminé','Heading 1')
bullets([
 'Les exigences Must et les tests AT-01 à AT-08 sont satisfaits sur la plateforme de référence.',
 'Quatre applications locales reçoivent le même flux 2 MS/s via IPC sans perte serveur pendant 8 h.',
 'La GUI présente signal, paramètres, santé et clients sans dégrader le flux.',
 'La matrice de compatibilité indique clairement les combinaisons supportées et les limites.',
 'Installation, désinstallation, sécurité, licences et documentation opérateur sont validées.',
])

doc.core_properties.title='SDR_Bridge — Spécification logicielle'
doc.core_properties.subject='Acquisition USB SDRplay RSP1A, diffusion I/Q multi-client et compatibilité logicielle'
doc.core_properties.author='Équipe projet'
doc.save(OUT)
print(OUT)
