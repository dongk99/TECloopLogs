Start-Process "C:\Program Files\PuTTY\putty.exe" `
    -ArgumentList "-serial COM21 -sercfg 9600,8,n,1,N -sessionlog peltier.log"