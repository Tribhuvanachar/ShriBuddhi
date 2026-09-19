#include <stdio.h>
#include <conio.h>
#include <math.h>
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
      float m;
      double j,rm,rmc,rma,rmp,rm_fraction,integer,r,a,dc,da,bp,md,rg,ay,ssr;
      double ssrf,ssrii,ssrc,chk,rs,cm,cmf,cmii,rmpc,scm,chkc,cu,cmc,cma,upg;
      double cg,cp,cmp,cs,vya,vyg,thi,esh,drv,thig,nak,nakg,drvn,csa,upthi;
      long rm_integer,q,ssri,cmi,th;
      int rmci,rmai,n;
      clrscr();
      //printf("\nenter the ahargana");
       //scanf("%f", &m);
	 m=335674;drv=0.4;drvn=12.0;
      rm=(m-((m*2)/139)-(m/115589));
      printf("rm=%lf\n",rm);
      rm_fraction = modf(rm, &integer);
      rm_integer=(long)integer;
      q=rm_integer/30;
      a=rm_integer%30;
      r=q%12;
      r=r+a/30;
      rm=r+(rm_fraction/30);
      rm=rm+11.55154996;
      /* rm is the ravimadhya calculated*/
      if(rm>12)
       rm=rm-12;
      if(rm<2.6)
      rmc=rm+9.4;
      else
      rmc=rm-2.6;
      printf("\nrmc=%lf",rmc);
      rma=check(rmc);
      /*rmci=(int)rmc;
      if(rmci>9)
      rma=12-rmc;
      else if(rmci>6)
      rma=rmc-6;
      else if(rmci>3)
      rma=6-rmc;
      else
      rma=rmc;  */
      printf("\n rma=%lf",rma);
      rm_fraction = modf(rma, &integer);
      rm_integer=(long)integer;
      rmai=(int)(rm_fraction*30);
      n=(rm_integer*30)+rmai;
      printf("\nn= %d",n);
      da=(double)n/30;
      printf("\nda=%lf",da);
       dc=(rma-da)*30; /*to convert from rashi to amsha*/
       printf("\n dc=%lf",dc);

     if(n<=15)
	   { rmp=((2.222222*n)+(dc*2.216667));
	     md=(2.213333-(0.01*(n-1)));
	    }
      else if(n<=30)
	    {
	      rmp=((33.333333+(2.078853*(n-15)))+(dc*2.083333));
	      md=(2.066666-(0.016667*(n-16)));
	      }
      else if(n<=45)
	    {
	       rmp=((64.516667+(1.792115*(n-30)))+(dc*1.8));
	       md=(1.8-(0.028888*(n-31)));
	       }

      else if(n<=60)
	   {
	    rmp=((91.4+(1.362007*(n-45)))+(dc*1.366667));
	    md=(1.366666-(0.034444*(n-46)));
	     }
      else if(n<=75)
	  {
	    rmp=((111.833333+(0.860215*(n-60)))+(dc*0.85));
	    md=(0.85-(0.037777*(n-61)));
	    }
      else if(n<=90)
	  {
	    rmp=((124.733333+(0.286738*(n-75)))+(dc*0.283333));
	    md=(0.283333-(0.018888*(n-76)));
	    }
      printf("\nrmp=%lf",rmp);
      bp=(rmp/360)+rmp;

      printf("\nbp=%lf",bp);
      if((rmc>3)&&(rmc<9))
      rg=59.133333+md;//karka gathi  where 59.133333 is ravi phala
      else
      rg=59.133333-md;//makara gathi
      //printf("rgk=%lf",59.13333+md);
      printf("\nrg=%lf",rg);
      /*computation of ravi gathi*/
      /*manda_spashta_ravi*/
      if(rmc<6)
      rm=rm-(bp/1800);
      else
      rm=rm+(bp/1800);
      printf("\nrm=%lf",rm);
      /*calculation of ayanamsha*/
      ay=0.79765741+((m-333529)/756000); // to be altered every ten years
      ssr=rm+ay; //sayana spashta ravi
      printf("\nssr=%lf",ssr);
	  /* rmci=(int)ssr;
     printf("\nrmci=%d",rmci);
      if(ssr>9)
      rma=12-ssr;
      else if(ssr>6)
      rma=ssr-6;
      else if(ssr>3)
      rma=6-ssr;
      else
      rma=ssr;
      //printf("\n rma=%lf",rma); */
      ssrc=check(ssr);   //to fix ssr in first quadrant
      printf("\nin first quad ssr=%lf",ssrc);
      ssrf=modf(ssrc,&ssrii);
      ssri=(long)ssrii;
      if(ssrc<1)
      chk=26*ssrf;  //chara khanda
      else if(ssrc<2)
      chk=26+(21*ssrf);
      else
      chk=47+(9*ssrf);
      printf("\n chk=%lf",chk);
      /*calculation of ravi sputa*/
       if(ssr<6)
       rs=rm-(chk/108000);
       else
       rs=rm+(chk/108000);

       printf("\n ravi sputa=%lf",rs);

       /*end of ravi sputa*/
       //calculation of chandra madhya

       cm=((13*m)+((3*m)/17)-(m/8315));
       printf("\n cm=%lf",cm);
       cmf=modf(cm,&cmii);
       cmi=(long)cmii;
       printf("\n cmi=%ld, cmf=%lf",cmi,cmf);
       q=cmi/30;
       a=cmi%30;
       r=q%12;
       r=r+a/30;
       cm=r+(cmf/30);

       cm=cm+11.91013703;
       if(cm>12)
       cm=cm-12;
       printf("\n cm=%lf",cm);
       rmpc=rmp/49200;
       if(rmc>6)
       cm=cm+rmpc;
       else
       cm=cm-rmpc;
       printf("\n cm=%lf",cm);
       chkc=(chk*120)/972000;
       printf("\n chkc=%lf",chkc);
       if(ssr>6)
       scm=cm+chkc;  //samskruta chandra madhya
       else
       scm=cm-chkc;
	printf("\n samskruta cm=%lf",scm);
	/*calculation of chandra_uchha*/
       cu=(m+(m/440))/9+(m/(467220));
       rm_fraction=modf(cu,&integer);
       rm_integer=(long)integer;
       q=rm_integer/30;
       a=rm_integer%30;
       r=q%12;
       r=r+a/30;
       cu=r+(rm_fraction/30);
	cu=cu+1.19402724;
	printf("\ncu=%lf",cu );
	if(cu>12)
	cu=cu-12;
	if(cu>scm)
	cmc=scm+12-cu;//kendra
	else
	cmc=scm-cu;
	printf("\ncmc=%lf",cmc);
	cma=check(cmc);
	printf("\n cma=%f",cma);
      rm_fraction = modf(cma, &integer);
      rm_integer=(long)integer;
      rmai=(int)(rm_fraction*30);
      n=(rm_integer*30)+rmai;
      printf("\nn= %d",n);
      da=(double)n/30;
      printf("\nda=%lf",da);
       dc=(cma-da)*30; /*to convert from rashi to amsha*/
       printf("\n dc=%lf",dc);
       //calculation of chandra_manda_phala and chandra_gathi
       if(n<=15)
	   { cmp=(5.166666*n)+(dc*5.166666);
	     md=(68.2-(0.293333*(n-1)));
	    }
      else if(n<=30)
	    {
	      cmp=(82.333333+(4.833333*(n-16)))+(dc*4.833333);
	      md=(63.8-(0.586666*(n-16)));
	      }
      else if(n<=45)
	    {
	       cmp=(154.166666+(4.166666*(n-31)))+(dc*4.166666);
	       md=(55.0-(0.88*(n-31)));
	       }

      else if(n<=60)
	   {
	    cmp=(215.666666+(3.166666*(n-46)))+(dc*3.166666);
	    md=(41.8-(1.026666*(n-46)));
	     }
      else if(n<=75)
	  {
	    cmp=((262.0+(2.0*(n-61)))+(dc*2.0));
	    md=(26.4-(1.173333*(n-61)));
	    }
      else if(n<=90)
	  {
	    cmp=(290.666666+(0.666666*(n-76)))+(dc*0.666666);
	    md=(8.8-(0.628521*(n-76)));
	    }
      printf("\ncmp=%lf",cmp);
      cp=790.583333;
      if(cmc>3&&cmc<9)
      cg=cp+md;
      else
      cg=cp-md;
      printf("\ncg=%lf",cg);
      //calculation of chandra_sphuta
      if(cmc>6)
      cs=scm+(cmp/1800);
      else
      cs=scm-(cmp/1800);
      printf("\nchandra_sphuta=%lf",cs);
      //calculation of vyarka and vyarka_gathi
      if(cs<rs)
      {csa=cs+12;
      vya=csa-rs;}
      else
      vya=cs-rs;
      vyg=cg-rg;
      printf("\nvya=%lf \nvyg=%lf", vya,vyg);
      //calculation of tithi
     // drv=4.8;
      esh=drv-vya; printf("esh=%lf",esh);
      thi=(esh*108000)/vyg;
      rm_fraction=modf(thi,&integer);
      thig=ceil(rm_fraction*60);//conversion to galige
      th=(long)thi;
      if((esh+0.4)<(vyg/1800))
      {upthi=43200/vyg;
      rm_fraction=modf(upthi,&integer);
      upg=ceil(rm_fraction*60);
      printf("\n\nuparitithi=%ld_%lf",(long)upthi,upg);}
      printf("\n\ntithi=%ld-%lf",th,thig);
     // if(cs>rs)
     // cs=cs-12;
      esh=(drvn-cs);
      nak=(esh*108000)/cg;
      rm_fraction=modf(nak,&integer);
      nakg=ceil(rm_fraction*60);
      printf("\n\nnakshatra=%ld-%lf",(long)nak,nakg);
      getch();





	   }