from database.queries import USER_LIST
from utils.helpers import hash_password
class UsuarioModel:
    def __init__(self,db): self.db=db
    def authenticate(self,usuario,password,verify_password):
        with self.db.cursor() as (_,c):
            c.execute("SELECT id,nombre,usuario,password_hash,rol,estado FROM usuarios WHERE usuario=%s LIMIT 1",(usuario,)); row=c.fetchone()
            if not row or row['estado']!='Activo' or not verify_password(password,row['password_hash']): return None
            row.pop('password_hash',None); return row
    def list_all(self):
        with self.db.cursor() as (_,c): c.execute(USER_LIST); return c.fetchall()
    def create(self,nombre,usuario,password,rol,estado):
        with self.db.cursor() as (con,c): c.execute("INSERT INTO usuarios(nombre,usuario,password_hash,rol,estado) VALUES(%s,%s,%s,%s,%s)",(nombre,usuario,hash_password(password),rol,estado)); con.commit()
    def update(self,i,nombre,usuario,password,rol,estado):
        with self.db.cursor() as (con,c):
            if password: c.execute("UPDATE usuarios SET nombre=%s,usuario=%s,password_hash=%s,rol=%s,estado=%s WHERE id=%s",(nombre,usuario,hash_password(password),rol,estado,i))
            else: c.execute("UPDATE usuarios SET nombre=%s,usuario=%s,rol=%s,estado=%s WHERE id=%s",(nombre,usuario,rol,estado,i))
            con.commit()
