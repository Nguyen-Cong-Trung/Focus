"""Portable backups validated in staging before any workspace file is replaced."""
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from datetime import datetime
import json
from contextlib import closing
import os
import shutil
import sqlite3
import zipfile
from utils.constants import load_config, update_config
from utils.validation import validate_mode, blocklist
from data.database import DatabaseManager, SCHEMA_VERSION
from data.models import FocusMode, CustomSound
from core.audio_library import inspect_wav


class BackupManager:
    def __init__(self, db, directory):
        self.db, self.directory = db, Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def export_workspace(self, destination):
        destination = Path(destination)
        if destination.resolve() == Path(self.db.db_path).resolve():
            raise ValueError('Choose a backup filename different from the workspace database.')
        temporary = destination.with_name(destination.name + '.' + uuid4().hex + '.tmp')
        try:
            with TemporaryDirectory(dir=self.directory) as folder:
                database = Path(folder)/'workspace.sqlite3'
                self.db.backup_to(database)
                manifest = {'format':'deep-focus-workspace','version':1,'sounds':[]}
                with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
                    archive.write(database,'workspace.sqlite3')
                    config = load_config()
                    config.pop('shutdown_record',None)
                    archive.writestr('settings.json',json.dumps(config))
                    # Query the snapshot, so sound IDs and records match the backed-up DB.
                    with closing(sqlite3.connect(database)) as conn:
                        sounds = conn.execute('SELECT id,file_path FROM custom_sounds').fetchall()
                    conn.close()
                    for ident, filename in sounds:
                        path = Path(filename)
                        member = f'sounds/{ident}.wav' if path.is_file() else None
                        if member: archive.write(path,member)
                        manifest['sounds'].append({'id':ident,'member':member})
                    archive.writestr('manifest.json',json.dumps(manifest))
            os.replace(temporary,destination)
        finally:
            temporary.unlink(missing_ok=True)
        return str(destination)

    def export_modes(self, destination):
        if Path(destination).resolve() == Path(self.db.db_path).resolve():
            raise ValueError('Choose an export filename different from the workspace database.')
        modes=[]
        with self.db.connection() as conn:
            for mode in self.db.get_all_modes():
                row=asdict(mode)
                row['items']=[dict(r) for r in conn.execute('SELECT item_type,value,enabled FROM blocked_items WHERE mode_id=?',(mode.id,))]
                modes.append(row)
        Path(destination).write_text(json.dumps({'format':'deep-focus-modes','version':1,'modes':modes},indent=2),encoding='utf-8')
        return str(destination)

    def import_modes(self, source):
        source=Path(source)
        if source.stat().st_size>2*1024*1024: raise ValueError('This mode file is too large.')
        payload=json.loads(source.read_text(encoding='utf-8'))
        if payload.get('format')!='deep-focus-modes' or payload.get('version')!=1:
            raise ValueError('Choose a Focus mode export.')
        incoming=payload.get('modes')
        if not isinstance(incoming,list) or not 1<=len(incoming)<=200:
            raise ValueError('The export must contain 1 to 200 modes.')
        names={m.name.casefold() for m in self.db.get_all_modes()}
        pending=[]
        for row in incoming:
            mode=FocusMode(**{k:v for k,v in row.items() if k in FocusMode.__dataclass_fields__ and k not in ('id','is_default')})
            if mode.auto_sound.startswith('custom_'): mode.auto_sound='none'
            validate_mode(mode)
            base=mode.name[:60]
            i=2
            while mode.name.casefold() in names:
                mode.name=f'{base} (imported {i})'
                i+=1
            names.add(mode.name.casefold())
            states={(r['item_type'],r['value'].casefold()):bool(r['enabled']) for r in row.get('items',[])}
            pending.append((mode,states))
        # Validate everything before this single transaction; no partial imports.
        with self.db.connection() as conn:
            for mode,states in pending:
                data=asdict(mode)
                del data['id']
                data['is_default']=0
                keys=list(data)
                ident=conn.execute(f"INSERT INTO focus_modes ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",list(data.values())).lastrowid
                self.db._replace_lists(conn,ident,json.loads(mode.blocked_sites),json.loads(mode.blocked_apps))
                for (kind,value),enabled in states.items():
                    conn.execute('UPDATE blocked_items SET enabled=? WHERE mode_id=? AND item_type=? AND lower(value)=?',(int(enabled),ident,kind,value))
        return len(pending)

    @staticmethod
    def _settings(config):
        if not isinstance(config,dict): raise ValueError('The backup settings are invalid.')
        result={}
        for key in ('global_hotkeys','close_to_tray'):
            if key in config:
                if type(config[key]) is not bool: raise ValueError('Invalid preference in backup.')
                result[key]=config[key]
        if config.get('theme') in ('light','dark'): result['theme']=config['theme']
        for key,kind in (('hardcore_sites','website'),('hardcore_apps','app')):
            if key in config: result[key]=blocklist(config[key],kind)
        if isinstance(config.get('active_mode'),str): result['active_mode']=config['active_mode']
        return result

    def restore_workspace(self, source):
        new_files=[]
        prior=None
        previous=load_config()
        try:
            with TemporaryDirectory(dir=self.directory) as folder:
                folder=Path(folder)
                with zipfile.ZipFile(source) as archive:
                    infos=archive.infolist()
                    if len({i.filename for i in infos})!=len(infos) or sum(i.file_size for i in infos)>512*1024*1024:
                        raise ValueError('The backup is too large or contains duplicate entries.')
                    if archive.getinfo('manifest.json').file_size>1024*1024 or archive.getinfo('settings.json').file_size>1024*1024:
                        raise ValueError('The backup metadata is too large.')
                    manifest=json.loads(archive.read('manifest.json'))
                    if manifest.get('format')!='deep-focus-workspace' or manifest.get('version')!=1:
                        raise ValueError('Choose a Focus workspace backup.')
                    settings=self._settings(json.loads(archive.read('settings.json')))
                    incoming=folder/'incoming.sqlite3'
                    if archive.getinfo('workspace.sqlite3').file_size>64*1024*1024:
                        raise ValueError('The backup database is too large.')
                    incoming.write_bytes(archive.read('workspace.sqlite3'))
                    with closing(sqlite3.connect(incoming)) as check:
                        check.execute('PRAGMA trusted_schema=OFF')
                        if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('The backup database is damaged.')
                        version=check.execute('PRAGMA user_version').fetchone()[0]
                        if version>SCHEMA_VERSION: raise ValueError('This backup needs a newer Focus version.')
                        if check.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR sql LIKE '%VIRTUAL TABLE%'").fetchone():
                            raise ValueError('Unsupported database objects in backup.')
                        tables={r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if not {'focus_modes','focus_sessions','blocked_items','custom_sounds'}<=tables:
                            raise ValueError('The backup database is incomplete.')
                    check.close()
                    candidate=DatabaseManager(incoming,settings.get('active_mode','Default'))
                    for mode in candidate.get_all_modes(): validate_mode(mode)
                    members={row['id']:row['member'] for row in manifest.get('sounds',[])}
                    sounds=self.directory/'sounds'
                    sounds.mkdir(exist_ok=True)
                    missing=0
                    for sound in candidate.get_all_custom_sounds():
                        member=members.get(sound.id)
                        if member is None:
                            candidate.delete_custom_sound(sound.id)
                            missing+=1
                            continue
                        if member!=f'sounds/{sound.id}.wav' or archive.getinfo(member).file_size>64*1024*1024:
                            raise ValueError('Invalid sound entry in backup.')
                        staged=folder/f'{sound.id}.wav'
                        with archive.open(member) as src, staged.open('wb') as dest:
                            shutil.copyfileobj(src,dest)
                        inspect_wav(staged)
                        target=sounds/(uuid4().hex+'.wav')
                        shutil.move(str(staged),str(target))
                        new_files.append(target)
                        sound.file_path=str(target)
                        candidate.update_custom_sound(sound)
                backups=self.directory/'backups'
                backups.mkdir(exist_ok=True)
                prior=backups/f'before-restore-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.zip'
                self.export_workspace(prior)
                rollback=folder/'rollback.sqlite3'
                self.db.backup_to(rollback)
                try:
                    # SQLite backup keeps replacement consistent without an open-file rename.
                    with closing(sqlite3.connect(incoming)) as src, closing(sqlite3.connect(self.db.db_path)) as dest:
                        src.backup(dest)
                    src.close()
                    dest.close()
                    update_config(settings)
                except Exception:
                    with closing(sqlite3.connect(rollback)) as src, closing(sqlite3.connect(self.db.db_path)) as dest:
                        src.backup(dest)
                    src.close()
                    dest.close()
                    update_config(previous)
                    raise
            return {'backup':str(prior),'missing_sounds':missing}
        except Exception:
            for path in new_files: path.unlink(missing_ok=True)
            raise
