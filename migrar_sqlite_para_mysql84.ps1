Param(
    [string]$ProjectDir = $PSScriptRoot
)
$MYSQL84="C:\Program Files\MySQL\MySQL Server 8.4\bin"
$DATADIR="C:\mysql84\data"
$PORT=3307
$ROOTPWD='Nacari97$'
$DB='ncfly'
$DBUSER='ncfly_user'
$DBPWD='Nacari97$'

Set-Location $ProjectDir

if (!(Test-Path $DATADIR)) {
  New-Item -ItemType Directory -Force -Path $DATADIR | Out-Null
  & "$MYSQL84\mysqld.exe" --initialize-insecure --datadir="$DATADIR"
}

$running = Get-Process mysqld -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$MYSQL84\mysqld.exe" }
if (!$running) {
  Start-Process -NoNewWindow -FilePath "$MYSQL84\mysqld.exe" -ArgumentList "--datadir=$DATADIR","--port=$PORT","--console"
  Start-Sleep -Seconds 5
}

& "$MYSQL84\mysql.exe" -h 127.0.0.1 -P $PORT -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$ROOTPWD'; FLUSH PRIVILEGES;"
& "$MYSQL84\mysql.exe" -h 127.0.0.1 -P $PORT -u root -p$ROOTPWD -e "CREATE DATABASE IF NOT EXISTS $DB DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;"
& "$MYSQL84\mysql.exe" -h 127.0.0.1 -P $PORT -u root -p$ROOTPWD -e "CREATE USER IF NOT EXISTS '$DBUSER'@'localhost' IDENTIFIED BY '$DBPWD'; GRANT ALL PRIVILEGES ON $DB.* TO '$DBUSER'@'localhost'; FLUSH PRIVILEGES;"

$env:DB_ENGINE="sqlite"
python -V >$null 2>&1
if ($LASTEXITCODE -ne 0) { $pycmd="py" } else { $pycmd="python" }

& $pycmd manage.py dumpdata --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission --exclude=admin.logentry --indent 2 > dump.json

$env:DB_ENGINE="mysql"
$env:MYSQL_DB=$DB
$env:MYSQL_USER=$DBUSER
$env:MYSQL_PASSWORD=$DBPWD
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="$PORT"

& $pycmd manage.py migrate --noinput
& $pycmd manage.py loaddata dump.json
& $pycmd manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['HOST'], connection.settings_dict['PORT'])"
