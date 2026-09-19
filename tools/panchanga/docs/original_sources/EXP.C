#include<stdio.h>
#include<conio.h>
#include<math.h>
double check(double rmc1)
      {
      int rmci;double rma1;

      if(rmc1>9)
      rma1=12-rmc1;
      else if(rmc1>6)
      rma1=rmc1-6;
      else if(rmc1>3)
      rma1=6-rmc1;
      else
      rma1=rmc1;
      return rma1;
      }

void main()
{
int cnt=0;
float m=702;double ay;
double rm,rm1,rmr,rm_frac,integer,rmk,rmc,rma,theeta,rmc1,bp,cmc1,cma,cmpa,cmp;
double rmp,rmpa,rmp1,r,a,msr,msr1,rg,ssr,cm_frac,cmk,cm1,cu,cu1,msc1,msc,no_naks;
double ayx,ayf,ayi,jya,ssrf,ssrii,ssrc,chk,rs,cm,scm1,scm,a1,b,cuk,cu1_frac,mscx,x,x_frac,no_tithi,tithi;
double cg,cs,vya,vyg,thi,esh,drv,thig,nak,nakg,drvn,csa,upthi,chkr,chkc,tithi_fraction,rm_fraction,upg,th;
char th_name[30][15]={"s.paadya","s.dwiteeya","s.triteeya","s.chaturti","s.panchami","s.shashti","s.sapthami","s.ashtami",
		     "s.navami","s.dashami","s.ekadashi","s.dwadashi","s.trayodashi","s.chaturdashi","poornima",
		     "k.paadya","k.dwiteeya","k.triteeya","k.chaturti","k.panchami","k.shashti","k.sapthami","k.ashtami",
		     "k.navami","k.dashami","k.ekadashi","k.dwadashi","k.trayodashi","k.chaturdashi","amavaasya"};
char nk_name[27][15]={"ashwini","bharani","krithika","rohini","mrugashira","aardra","punarvasu","pushyaa",
		     "aashlesha","makha","pubba","uttara","hasta","chitta","swathi",
		     "vishaka","anuradha","jyeshta","moola","poorvaashada","uttaraashada","shravana","dhanishta",
		     "shatabisha","poorvabhadra","uttarabhadra","revathi"};
clrscr();
rmr=m*31/11323;//rm rashyadi
rm_frac=modf(rmr,&integer);
printf("int=%lf",integer);
ayx=(integer+5114)/615;
ayx=check(ayx);
ayx=ayx*3;
ayf=modf(ayx,&ayi);
if(ayi<1)
jya=242*ayf;
else
if(ayi<2)
jya=242+(237*ayf);
else
if(ayi<3)
jya=479+(224*ayf);
else
if(ayi<4)
jya=703+(205*ayf);
else
if(ayi<5)
jya=908+(180*ayf);
else
if(ayi<6)
jya=1088+(149*ayf);
else
if(ayi<7)
jya=1237+(110*ayf);
else
if(ayi<8)
jya=1347+(69*ayf);
else
if(ayi<9)
jya=1416+(24*ayf);
ay=jya/1800;
printf("ayanamsha=%lf",ay);
rmk=m/18047400;//m*3/30079-kalaadi
rm=rm_frac*12-rmk;    //chakradi is converted rashyadi
rm1=rm=rm+11.937748;
L1: if(rm>12)
rm=rm-12;
printf("rm=%lf",rm);
 if(rm<2.6)
      rmc=rm+9.4;
      else
      rmc=rm-2.6;
  //    printf("\nrmc=%lf",rmc);
      if(cnt==0)
      rmc1=rmc;
      rma=check(rmc);
       printf("\nrma=%lf",rma);
       //mandaphala calculation
      rmpa=3438*sin(11*rma/21);   //30*rma*22/(7*180)in radians
      rmp=rmpa*3/80;
      if(cnt==0)
      rmp1=rmp;  printf("rmp1=%lf",rmp1);
    //  printf("\nrmp=%lf",rmp);
      bp=(rmp/360)+rmp;        //rmp/6*60 convert to vikale
      printf("bp=%lf",bp);
       if(rmc<6)
      msr=rm-(bp/1800);
      else
      msr=rm+(bp/1800);
      if(cnt==0)msr1=msr;printf("msr1=%lf",msr1);
      printf("msr=%lf",msr);cnt++;
      rm=rm1+0.0328534;
      if(cnt==1)goto L1;
      if(msr1>msr)
      rg=msr+12-msr1;
      else
      rg=msr-msr1;
      printf("rg=%lf",rg);
    //  printf("\nint=%ld",(long)integer);
      cnt=0;
      //calcn of chandra mahya
cm=m*600/16393;//cm rashyadi
cm_frac=modf(cm,&r);
//cmk=m/5256240;   //m*15/43802 kalaadi
cmk=(m*7)/36781200;//corrected factor printf("\n cmk=%lf",cmk);
cm=cm_frac*12-cmk;    //chakradi is converted rashyadi
cm1=cm=cm+1.303107;//-0.000833;deemed correction for tithinirnaya
if(cm>12)
cm=cm-12;
printf("\n cm=%lf",cm);
a1=rmp1/49200;  //rmp1*3/82 kala convtd to rashi
if(rmc1<6)
scm1=cm-a1;
else
scm1=cm+a1;
if(scm1>12)
scm1=scm1-12;
 printf("scm1=%lf",scm1);
 cm=cm1+0.439212;
 if(cm>12)
cm=cm-12;
a=rmp/49200;  //rmp1*3/82 kala convtd to rashi
if(rmc<6)
scm=cm-a;
else
scm=cm+a;
if(scm>12)
scm=scm-12;
 printf("scm=%lf",scm);
 //calcn of chandra uchha
cu1=m/3232;// printf("\ncu1=%lf",cu1);
cu1_frac=modf(cu1,&b);           //  printf("\ncu1_frac=%lf",cu1_frac);
//cuk=m/1383210;// printf("\ncuk=%lf",cuk); //m*40/30738 kala convtd to rashi
cuk=(m*7)/9338400;//corrected factor
cu1=cu1_frac*12-cuk;  //    printf("\ncu1=%lf",cu1);
cu1=cu1+2.009663;//-0.006935;deemed correction
//printf("\ncu1=%lf",cu1);
if(cu1>12)
cu1=cu1-12;
cu=cu1+0.003712;
if(cu>12)
cu=cu-12;
L2:if(cu1>scm1)
cmc1=scm1+12-cu1;
else
cmc1=scm1-cu1;
//printf("\ncmc1=%lf",cmc1);
cma=check(cmc1);

 //mandaphala calculation
  cmpa=3438*sin(11*cma/21);   //30*rma*22/(7*180)in radians
     cmp=cmpa*7/80;
  if(cmc1<6)
      mscx=scm1-(cmp/1800);
      else
      mscx=scm1+(cmp/1800);
   if(mscx<0)
   mscx=mscx+12.0;
   if(cnt==0)
      msc1=mscx;
      printf("msc1=%lf",msc1);
   cnt++;cu1=cu;scm1=scm;msc=mscx;
   if(cnt==1)
   goto L2;
   printf("msc=%lf",msc);
 if(msc1>msc)
 cg=msc+12-msc1;
 else
 cg=msc-msc1;printf("cg=%lf",cg);

 ssr=msr1+ay; printf("\nssr=%lf",ssr);
 if(ssr>12)
 ssrf=ssr=ssr-12;
 else
 ssrf=ssr; printf("\nssrf=%lf",ssrf);
 ssr=check(ssr);
ssr=ssr*30;
// printf("\nssr=%lf",ssr);
 if(ssr<=10)
 chk=102*ssr;
 else if(ssr<=20)
 chk=1020+((ssr-10)*99.9);
 else if(ssr<=30)
 chk=2019+((ssr-20)*97.8);
  else if(ssr<=40)
 chk=2997+((ssr-30)*91.7);
  else if(ssr<=50)
 chk=3914+((ssr-40)*79.9);
  else if(ssr<=60)
 chk=4713+((ssr-50)*67.8);
  else if(ssr<=70)
 chk=5391+((ssr-60)*54.7);
  else if(ssr<=80)
 chk=5938+((ssr-70)*33.3);
  else if(ssr<=90)
 chk=6271+((ssr-80)*11.9);//in vikale
 chk=chk/2;  //charaardha in vikale
 chkr=chk*rg/2;  //charaardha*rg/3600 in vikale
 chkc=chk*cg/2;  //-------------"-------------
  printf("\nchkc=%lf",chkc);
  printf("\nchkr=%lf",chkr);
 if(ssrf<6)
{ rs=msr1-chkr/108000;
 cs=msc1-chkc/108000;}
 else
 { rs=msr1+chkr/108000;
 cs=msc1+chkc/108000;}
 printf("\nrs=%lf",rs);
 printf("\ncs=%lf",cs);
 if(rs>cs)
 vya=cs+12-rs;
 else
 vya=cs-rs;
  printf("\nvya=%lf",vya);
 vyg=cg-rg;//in rashi
  printf("\nvyg=%lf",vyg);
 x=vya*2.5;
 x_frac=modf(x,&no_tithi);
 no_tithi+=1;
// printf("\n\nno_tithi=%lf",no_tithi);
printf("\n\ntithi=%s",th_name[no_tithi-1]);
 esh=0.4*(1.0-x_frac);//in  rashi
 tithi=esh*60/vyg; //printf("\ntithi=%lf",tithi);
 tithi_fraction=modf(tithi,&integer);
      thig=ceil(tithi_fraction*60);// printf("\nthig=%lf",thig);//conversion to galige
      th=(long)tithi; //printf("\ntithi=%lf",th);
      if((esh+0.4)<vyg)
      {upthi=24/vyg;  //60*720/vyg in kale convtd to rashi
      rm_fraction=modf(upthi,&integer);
      upg=ceil(rm_fraction*60);printf("\nuparitithi=%s",th_name[no_tithi]);
      printf("\n\nuparitithi=%ld-%ld",(long)upthi,(long)upg);}
      printf("\ntithi=%ld-%ld",(long)th,(long)thig);
      x=cs*2.25;
      x_frac=modf(x,&no_naks);
      no_naks+=1;
  printf("\n\nnakshatra=%s",nk_name[no_naks-1]);
      esh=4*(1-x_frac)/9;
      nak=esh*60/cg;
       rm_fraction=modf(nak,&integer);
      nakg=ceil(rm_fraction*60);
      printf("\nnakshatra=%ld-%ld",(long)nak,(long)nakg);
       getch();

    }
