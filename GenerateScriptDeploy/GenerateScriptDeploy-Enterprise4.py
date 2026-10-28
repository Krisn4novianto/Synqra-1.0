#!/usr/bin/env python3
"""Read-only DataSourceDistributor deployment SQL generator.
Run: python3 generateScriptDeploy/DataSourceDistributor-generateScriptDeploy.py
Requires db_config.SERVERS and db_connection.connect_sqlserver.
"""
from __future__ import annotations
import re
import sys
from datetime import datetime, date, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'DataSourceDistributor'

COMMON = 'LogActivityModul LogActivitySubModul LogActivityEntity'.split()
BASE = {
 'ParamDDHIST': 'FieldSelectTrue FieldSelectFalse Rekening WhereCondition TableTrueDestination TableFalseDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamWay4CardPostingData': 'FieldSelectTrue FieldSelectFalse WhereCondition TableTrueDestination TableFalseDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamCPD13055': 'FieldSelectTrue FieldSelectFalse WhereCondition TableTrueDestination TableFalseDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamDDTRN': 'FieldSelect Rekening WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive SchStart',
 'ParamTLLOG': 'FieldSelect WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamTLLOG24': 'FieldSelect WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamPSW': 'FieldSelect WhereCondition TableSource TableDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamESB': 'FieldSelect WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive SchStart',
 'ParamFTP': 'Action FTPType FTPAddress FTPPort FTPUser FTPPass FTPPassPhrase FTPisPassive FTPencryption UseProxy FTPPath LocalPath Filename LogActivityModul LogActivitySubModul LogActivityEntity LogActivityFilenameDateAdd Note isActive',
 'ParamParseFile': 'LocalPath Filename TableDestination FieldFilename FieldFiledate LogActivityModul LogActivitySubModul LogActivityEntity LogActivityFilenameDateAdd IsFixedCol Delimiter HeaderRowSkip FooterRowSkip TextQualifier Note isActive',
 'ParamGenerateFile': 'LocalPath Filename FieldSelect TableSource WhereCondition DateCol isSourceFromSP SPName LogActivityModul LogActivitySubModul LogActivityEntity LogActivityFilenameDateAdd isHeader Delimiter TextQualifier isActive Note',
 'ParamZipFile': 'Action SourcePath FileName Extension Password DestinationPath isMoveToBackUp BackupPath IPServer LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive Note',
 'ParamInqCardno': 'TableName WhereCondition DataDateField CardnoField AccountnoFieldUpdate NameFieldUpdate BranchCodeFieldUpdate TypeCodeFieldUpdate CardStatusFieldUpdate CIFFieldUpdate CardTypeFieldUpdate TypeFieldUpdate WhereFieldUpdateCheck IsUseLogActivity LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive Note',
 'ParamTLJBH0': 'FieldSelect WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity TranCode FieldDateTime Note isActive',
 'ParamBRD330': 'FieldSelectTrue FieldSelectFalse WhereCondition TableTrueDestination TableFalseDestination LogActivityModul LogActivitySubModul LogActivityEntity Note isActive',
 'ParamESBRevamp': 'FieldSelect WhereCondition TableDestination LogActivityModul LogActivitySubModul LogActivityEntity isActive Note SchStart',
 'ParamEMAIL': 'Divisi Product Fitur EmailTo EmailCC Subject IsContentFromSP ContentEmail LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive Note',
}

CHILD = {
 'ParamFTPCekLogActivity': ('ParamFTP','IDParamFTP','ID','LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive'),
 'ParamParseFileCekLogActivity': ('ParamParseFile','IDParamParseFile','ID','LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive'),
 'ParamParseFileMappingColumn': ('ParamParseFile','IDParamParseFile','ID','Col FieldTargetName FixedColSubstring'),
 'ParamGenerateFileCekLogActivity': ('ParamGenerateFile','IDParamGenerateFile','ID','LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive'),
 'ParamZipFileCekLogActivity': (None,'IDFitur',None,'LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd IsActive'),
 'ParamInqCardnoCekLogActivity': ('ParamInqCardno','IDParamInqCardno','ID','LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive'),
 'ParamEMAILCekLogActivity': ('ParamEMAIL','IDParamEMAIL','IDParamEmail','LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd isActive'),
 'ParamEMAILAttachmentFile': ('ParamEMAIL','IDParamEMAIL','IDParamEmail','OrderBy LogActivityFilenameDateAdd FileLocalPath FileName IsDeleteFileOnFTPAferSent'),
}

TABLES = list(BASE) + list(CHILD)


def q(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
        raise ValueError('Invalid SQL identifier: '+name)
    return '['+name+']'


def lit(value):
    if value is None: return 'NULL'
    if isinstance(value,bool): return '1' if value else '0'
    if isinstance(value,(int,Decimal)): return str(value)
    if isinstance(value,float): return repr(value)
    if isinstance(value,bytes): return '0x'+value.hex()
    if isinstance(value,(date,datetime,time)): value=value.isoformat(sep=' ') if isinstance(value,datetime) else value.isoformat()
    return "N'"+str(value).replace("'","''")+"'"


def predicate(values, aliases=None):
    return ' AND '.join((f'{q(k)} IS NULL' if v is None else f'{q(k)} = {lit(v)}') for k,v in values.items()) or '1=1'


def select(cur,table,columns,where,args):
    sql=f'SELECT {", ".join(q(c) for c in columns)} FROM dbo.{q(table)} WHERE {where}'
    cur.execute(sql,*args)
    names=[x[0] for x in cur.description]
    return [dict(zip(names,row)) for row in cur.fetchall()]


def get(cur,table,columns,where,args):
    return select(cur,table,columns,where,args)


def choose(prompt,options):
    while True:
        print('\n'+prompt)
        for k,v in options.items(): print(f'  {k}. {v}')
        value=input('Pilihan: ').strip()
        if value=='0': sys.exit(0)
        if value in options: return value
        print('[ERROR] Pilihan tidak valid')


def safe(s):
    return re.sub(r'_+','_',re.sub(r'[^A-Za-z0-9_-]+','_',str(s or 'TanpaNamaModul'))).strip('_-')[:80] or 'TanpaNamaModul'


def sql_insert(table,values,where,comment):
    cols=', '.join(q(c) for c in values)
    vals=', '.join(str(v) for v in values.values())
    return [f'-- {comment}',f'IF NOT EXISTS (SELECT 1 FROM dbo.{q(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {where})',
            'BEGIN',f'    INSERT INTO dbo.{q(table)} ({cols}) VALUES ({vals});','END;','']


def full_match(row,fk_col,fk_expr):
    return ' AND '.join([f'{q(fk_col)} = {fk_expr}']+[f'{q(c)} IS NULL' if v is None else f'{q(c)} = {lit(v)}' for c,v in row.items()])


def generate(feature,targets,records,chosen,feature_id):
    all_tables = chosen is None
    selected=set(TABLES if all_tables else [chosen])
    if chosen in CHILD and CHILD[chosen][0]: selected.add(CHILD[chosen][0])
    # Parent ParamFitur is always included for FK resolution.
    lines=['-- DataSourceDistributor | Generate Script Deploy',f'-- Generated: {datetime.now():%Y-%m-%d %H:%M:%S}',
           f'-- Source IDFitur: {feature_id}',f'-- Source DBName: {feature["DBName"]}',
           '-- Scope: '+('All 25 activity tables' if all_tables else chosen),
           '-- REVIEW BEFORE EXECUTION. INSERT-if-missing; no UPDATE/DELETE.',
           '-- Sensitive values in FTP/ZIP/email configurations may be embedded in this SQL.',
           '-- Run using SQLCMD mode. PasswordProd is a textual SQLCMD substitution.',
           '-- SQLCMD password values containing apostrophes require special handling.',
           'USE [DataSourceDistributor];','GO','SET XACT_ABORT ON;','BEGIN TRY','    BEGIN TRANSACTION;','']
    server_where=predicate({'IPServer':targets['host'],'DBName':feature['DBName']})
    feature_values={'IPServer':lit(targets['host']),'DBName':lit(feature['DBName']),
                    'DBUser':lit(targets['user']),
                    'DBPass':f"dbo.fnEncrypt(N'$(PasswordProd)', {lit(targets['host']+'BR!')})",'DBType':lit('mssql')}
    lines+=sql_insert('ParamFitur',feature_values,server_where,'Parent ParamFitur')
    lines+=['DECLARE @IDFitur INT;',f'SELECT @IDFitur = IDFitur FROM dbo.ParamFitur WHERE {server_where};',
            "IF @IDFitur IS NULL THROW 51001, N'ParamFitur target tidak ditemukan', 1;",
            f'IF (SELECT COUNT_BIG(*) FROM dbo.ParamFitur WHERE {server_where}) <> 1 THROW 51002, N\'ParamFitur target duplikat\', 1;','']
    parent_vars={}
    for table in BASE:
        if table not in selected: continue
        cols=BASE[table].split()
        for idx,row in enumerate(records.get(table,[]),1):
            nonfk={c:row[c] for c in cols}
            vals={'IDFitur':'@IDFitur',**{c:lit(v) for c,v in nonfk.items()}}
            cond=full_match(nonfk,'IDFitur','@IDFitur')
            lines+=sql_insert(table,vals,cond,f'{table} row {idx}')
            # Resolve parent target PK when a child depends on it.
            if any(spec[0]==table and child in selected for child,spec in CHILD.items()):
                pk=next(spec[2] for spec in CHILD.values() if spec[0]==table)
                var=f'@P_{table}_{idx}'
                lines += [f'DECLARE {var} INT;',f'SELECT {var} = {q(pk)} FROM dbo.{q(table)} WHERE {cond};',
                          f"IF {var} IS NULL THROW 51003, N'Parent target tidak ditemukan', 1;",
                          f"IF (SELECT COUNT_BIG(*) FROM dbo.{q(table)} WHERE {cond}) <> 1 THROW 51004, N'Parent target tidak unik', 1;",'']
                parent_vars[(table,row['__pk'])]=var
    for table,spec in CHILD.items():
        if table not in selected: continue
        parent,fk,pk,cols_text=spec
        cols=cols_text.split()
        for idx,row in enumerate(records.get(table,[]),1):
            if parent:
                key=(parent,row['__parent_id'])
                if key not in parent_vars: raise RuntimeError(f'Missing parent for {table} row {idx}: {key}')
                fk_expr=parent_vars[key]
            else: fk_expr='@IDFitur'
            nonfk={c:row[c] for c in cols}
            vals={fk:fk_expr,**{c:lit(v) for c,v in nonfk.items()}}
            cond=full_match(nonfk,fk,fk_expr)
            lines+=sql_insert(table,vals,cond,f'{table} row {idx}')
    lines+=['    COMMIT TRANSACTION;',"    PRINT N'DEPLOY SUCCESS';",'END TRY','BEGIN CATCH',
            '    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;','    THROW;','END CATCH;','']
    return '\n'.join(lines),selected


def main():
    print('='*70+'\n DATASOURCEDISTRIBUTOR | GENERATE SCRIPT DEPLOY\n'+'='*70)
    servers={'1':SERVERS['2'],'2':SERVERS['3']}
    s=choose('Pilih server sumber (0=Keluar):',{k:f'{v.name}:{v.port}' for k,v in servers.items()})
    opts={'1':'Semua tabel (25 tabel activity + ParamFitur)'}
    opts.update({str(i+2):t for i,t in enumerate(TABLES)})
    opts['0']='Keluar'
    selection=choose('Pilih tabel:',opts)
    chosen=None if selection=='1' else opts[selection]
    while True:
        try:
            fid=int(input('IDFitur sumber: ').strip())
            if fid>0: break
        except ValueError: pass
        print('[ERROR] IDFitur harus bilangan bulat positif')
    with connect_sqlserver(servers[s],DATABASE) as conn:
        cur=conn.cursor()
        feat=get(cur,'ParamFitur',['IDFitur','IPServer','DBName'],'IDFitur = ?',(fid,))
        if len(feat)!=1: raise RuntimeError(f'ParamFitur IDFitur {fid} ditemukan {len(feat)} baris')
        feature=feat[0]
        print(f"\nSumber: {feature['IPServer']} / {feature['DBName']}")
        host=input('IPServer production target: ').strip()
        user=input('DBUser production target: ').strip()
        if not host or not user or len(host)>100 or len(user)>100 or '\n' in host+user or '\r' in host+user:
            raise ValueError('IPServer / DBUser tidak valid (maksimal 100 karakter)')
        targets={'host':host,'user':user}
        records={}
        needed=set(TABLES if chosen is None else [chosen])
        if chosen in CHILD and CHILD[chosen][0]: needed.add(CHILD[chosen][0])
        for table in BASE:
            if table not in needed: continue
            cols=BASE[table].split()
            parent_needed=any(spec[0]==table and c in needed for c,spec in CHILD.items())
            pk=next((spec[2] for c,spec in CHILD.items() if spec[0]==table and c in needed),None)
            querycols=([pk] if parent_needed else [])+['IDFitur']+cols
            rows=get(cur,table,querycols,'IDFitur = ?',(fid,))
            for row in rows:
                if parent_needed: row['__pk']=row[pk]
            records[table]=rows
        for table,(parent,fk,pk,cols_text) in CHILD.items():
            if table not in needed: continue
            cols=cols_text.split()
            if parent:
                sql=(f'SELECT '+', '.join('c.'+q(c) for c in [fk]+cols)+f' FROM dbo.{q(table)} c '
                     f'INNER JOIN dbo.{q(parent)} p ON c.{q(fk)} = p.{q(pk)} WHERE p.IDFitur = ?')
                cur.execute(sql,fid)
                data=[dict(zip([fk]+cols,row)) for row in cur.fetchall()]
                for row in data: row['__parent_id']=row[fk]
            else: data=get(cur,table,['IDFitur']+cols,'IDFitur = ?',(fid,))
            records[table]=data
    print('\n=== PREVIEW ===')
    print(f'Sumber: {servers[s].name} | DB: {DATABASE} | IDFitur: {fid}')
    print(f'Target: {host} / {user} | DBName modul: {feature["DBName"]}')
    print('Scope:',chosen or 'Semua tabel')
    for table,rows in records.items(): print(f'  {table}: {len(rows)} baris')
    tanggal=datetime.now().strftime('%Y%m%d')
    filename=(f'SOP DataSourceDistributor_{tanggal}.sql' if chosen is None else
              f'SOP DataSourceDistributor_{chosen}_{safe(feature["DBName"])}_{tanggal}.sql')
    output=Path(__file__).resolve().parent/'output'
    path=output/filename
    print('Output:',path)
    if path.exists(): print('[WARNING] File sudah ada dan akan ditimpa')
    if input('Generate file SQL? [YA/TIDAK]: ').strip().lower() not in ('ya','yes'): print('Dibatalkan.');return
    sql,selected=generate(feature,targets,records,chosen,fid)
    output.mkdir(parents=True,exist_ok=True)
    path.write_text(sql,encoding='utf-8')
    try: path.chmod(0o600)
    except OSError: pass
    print(f'\n[OK] SQL dibuat: {path}\n[INFO] Database sumber tidak diubah; SQL belum dieksekusi.')
    print('[PENTING] SQLCMD PasswordProd diperlukan saat eksekusi. Review file karena dapat mengandung kredensial FTP/ZIP.')

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nDibatalkan.');sys.exit(130)
    except Exception as e: print('[ERROR]',e,file=sys.stderr);sys.exit(1)
