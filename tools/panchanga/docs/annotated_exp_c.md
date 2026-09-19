# EXP.C — annotated

Source: `TC_new_final.zip` → `TC_new_final/TC_new_final/BIN/EXP.C` (also
copied verbatim, with no annotations, at
`docs/original_sources/EXP.C`). Dated 6 Oct 2014 — the newest and most
complete of the four related programs in that archive
(`EKADHASI.C`, `TITHI-NI.C`, `TITH_EXP.CPP` being the others), and the one
its author pointed to as "the main file that does the job."

This is the **original file, unmodified** — every line of code below is
exactly what's in `EXP.C`. The comments marked `// NOTE:` are new, added
here to explain what each step computes and why; the comments *without*
`NOTE:` were already in the original source. Two real, reproducible bugs
are called out where they occur — see the summary at the end for how they
were confirmed (by compiling and running the actual program), and
`panchanga/legacy/exp_c_reference.py` in this same `tools/panchanga/` tree
for a working, bug-fixed Python port verified against a live run of this
exact file.

## What this program computes, in one paragraph

Given `m` (Ahargana — elapsed civil days from an epoch, hardcoded below
instead of taken as input), it computes the Sun's and Moon's sidereal
longitude using a handful of terms of a traditional Indian trigonometric
table, derives their angular separation ("elongation"), and from that
prints which of the 30 tithis (lunar days) is current — including both
`s.ekadashi` (Shukla/waxing-fortnight Ekadashi) and `k.ekadashi`
(Krishna/waning-fortnight Ekadashi) — plus how much of it remains, and
similarly for the current nakshatra (lunar mansion, 1 of 27). It does
**not** compute sunrise, and takes no location input at all — see the
summary at the end.

## Annotated source

```c
#include<stdio.h>
#include<conio.h>          // NOTE: DOS-only header (clrscr/getch below).
                            //       Not available on a modern compiler;
                            //       stub it out to build/run this today.
#include<math.h>

// NOTE: `check()` folds an angle given in "rashi" units (0-12, i.e.
// 0-360 degrees, 1 rashi = 30 degrees) into the first quadrant, [0,3]
// rashi (0-90 degrees). This is the standard trick for reusing a
// quarter-sine table across all four quadrants of a circle. It assumes
// its argument is ALREADY wrapped into [0,12) -- every call site is
// responsible for that, and one call site later in this file forgets to
// (see the "BUG" note at the nakshatra calculation, near the bottom).
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

void main()                // NOTE: `void main()` is non-standard C; a
                            //       modern compiler wants `int main()`.
{
int cnt=0;
float m=702;double ay;     // NOTE: `m` is the Ahargana -- the ONE input
                            //       this whole calculation depends on --
                            //       and it's hardcoded here rather than
                            //       read from the user or derived from a
                            //       calendar date. 702 is right at the
                            //       Kali Yuga epoch (day ~700 of an era
                            //       that began ~5,000 years ago): not a
                            //       real target date, almost certainly a
                            //       leftover value from testing the
                            //       ayanamsha subroutine below in
                            //       isolation. To use this program for
                            //       an actual date, `m` has to be
                            //       hand-computed and this file
                            //       recompiled -- there is no Gregorian
                            //       date to Ahargana converter anywhere
                            //       in this codebase.
double rm,rm1,rmr,rm_frac,integer,rmk,rmc,rma,theeta,rmc1,bp,cmc1,cma,cmpa,cmp;
double rmp,rmpa,rmp1,r,a,msr,msr1,rg,ssr,cm_frac,cmk,cm1,cu,cu1,msc1,msc,no_naks;
double ayx,ayf,ayi,jya,ssrf,ssrii,ssrc,chk,rs,cm,scm1,scm,a1,b,cuk,cu1_frac,mscx,x,x_frac,no_tithi,tithi;
double cg,cs,vya,vyg,thi,esh,drv,thig,nak,nakg,drvn,csa,upthi,chkr,chkc,tithi_fraction,rm_fraction,upg,th;
                            // NOTE: `drv`/`drvn` are declared here but
                            //       never used anywhere in this file --
                            //       dead variables. In the sibling
                            //       program EKADHASI.C they ARE used, as
                            //       hand-picked target elongation values
                            //       for finding the exact crossing time
                            //       of a chosen tithi/nakshatra boundary
                            //       (confirmed: drv=4.0 -> exactly the
                            //       Ekadashi-onset boundary, drv=4.4 ->
                            //       exactly the Ekadashi-end boundary).
                            //       This file inherited the variable
                            //       list from that lineage but replaced
                            //       the hand-picked-target approach with
                            //       the generic `no_tithi` calculation
                            //       further down, leaving drv/drvn as
                            //       vestige.

// NOTE: The 30 tithi names, Shukla (waxing) paksha first, then Krishna
// (waning) paksha. Index 10 (0-based) = "s.ekadashi"; index 25 =
// "k.ekadashi" -- this table is what lets the program name ANY tithi,
// Ekadashi included, generically, rather than having Ekadashi-specific
// logic anywhere.
char th_name[30][15]={"s.paadya","s.dwiteeya","s.triteeya","s.chaturti","s.panchami","s.shashti","s.sapthami","s.ashtami",
		     "s.navami","s.dashami","s.ekadashi","s.dwadashi","s.trayodashi","s.chaturdashi","poornima",
		     "k.paadya","k.dwiteeya","k.triteeya","k.chaturti","k.panchami","k.shashti","k.sapthami","k.ashtami",
		     "k.navami","k.dashami","k.ekadashi","k.dwadashi","k.trayodashi","k.chaturdashi","amavaasya"};
// NOTE: The 27 nakshatra names, in the standard order starting from
// Ashwini.
char nk_name[27][15]={"ashwini","bharani","krithika","rohini","mrugashira","aardra","punarvasu","pushyaa",
		     "aashlesha","makha","pubba","uttara","hasta","chitta","swathi",
		     "vishaka","anuradha","jyeshta","moola","poorvaashada","uttaraashada","shravana","dhanishta",
		     "shatabisha","poorvabhadra","uttarabhadra","revathi"};
clrscr();

// ============================================================
// NOTE: SECTION 1 -- Ayanamsha (precession offset, sidereal vs tropical)
// ============================================================
rmr=m*31/11323;//rm rashyadi
                            // NOTE: mean Sun's longitude in "rashi" units
                            //       (0-12), from a fixed daily-motion
                            //       ratio (31/11323 rashi/day). This is
                            //       the classical "madhyama graha"
                            //       (mean-planet) step: motion is
                            //       assumed uniform here; the true,
                            //       non-uniform motion is corrected for
                            //       later (the "manda-phala" steps).
rm_frac=modf(rmr,&integer);
printf("int=%lf",integer);
ayx=(integer+5114)/615;    // NOTE: 5114/615 -- an epoch-alignment
                            //       constant converting elapsed days
                            //       into a "years since some ayanamsha
                            //       reference epoch"-like quantity, fed
                            //       into the jya (sine) table below.
ayx=check(ayx);
ayx=ayx*3;
ayf=modf(ayx,&ayi);
// NOTE: `jya` is built from a 9-segment piecewise-linear table -- this
// IS a discretized quarter-sine table (values 242, 237, 224, 205, 180,
// 149, 110, 69, 24 are consecutive differences of a sine curve sampled
// every 10 degrees, in arcminutes, scaled to a radius of ~3438 -- the
// same "trijya" radius used again later in the manda-phala calculation).
// This piecewise interpolation is how the ayanamsha is derived
// analytically here, instead of being a hardcoded per-decade constant
// like it is in the sibling programs EKADHASI.C/TITHI-NI.C/TITH_EXP.CPP
// -- this is the single biggest functional improvement EXP.C has over
// those three.
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
ay=jya/1800;                // NOTE: convert from arcminutes (out of the
                            //       3438-radius scale) to rashi units.
                            //       `ay` = ayanamsha, in rashi.
printf("ayanamsha=%lf",ay);

// ============================================================
// NOTE: SECTION 2 -- Ravi (Sun) madhya -> manda-phala -> sphuta (true)
//                    position, and Ravi gati (Sun's daily motion)
// ============================================================
rmk=m/18047400;//m*3/30079-kalaadi
                            // NOTE: a small correction term ("kalaadi" =
                            //       seconds-and-below precision term).
rm=rm_frac*12-rmk;    //chakradi is converted rashyadi
rm1=rm=rm+11.937748;        // NOTE: "deemed correction" -- an epoch
                            //       offset constant, hand-fit for this
                            //       file specifically. The sibling files
                            //       use DIFFERENT values here
                            //       (11.949898 in TITHI-NI.C/
                            //       TITH_EXP.CPP), confirming each file
                            //       was independently recalibrated,
                            //       likely against a different reference
                            //       date. No source/derivation is given
                            //       for this number anywhere in the
                            //       codebase.
L1: if(rm>12)               // NOTE: `L1:` is a goto target. The block
                            //       below computes the Sun's TRUE
                            //       (manda-corrected) longitude at `rm`;
                            //       it is run ONCE for the seed value
                            //       `rm1` (cnt==0) and again for
                            //       `rm1+0.0328534` (a small time step
                            //       ahead) to get two closely-spaced
                            //       positions, whose difference below
                            //       (`rg`) gives the Sun's instantaneous
                            //       daily motion -- a numerical
                            //       derivative computed by finite
                            //       difference, rather than an
                            //       analytical rate formula.
rm=rm-12;
printf("rm=%lf",rm);
 if(rm<2.6)
      rmc=rm+9.4;
      else
      rmc=rm-2.6;            // NOTE: shifts the origin so the "apogee"
                            //       (point of slowest motion, where the
                            //       manda-phala correction is zero) is
                            //       at rmc=0, rather than at rm=0.
  //    printf("\nrmc=%lf",rmc);
      if(cnt==0)
      rmc1=rmc;
      rma=check(rmc);        // NOTE: fold into first quadrant [0,3]
                            //       rashi for the sine-table lookup.
       printf("\nrma=%lf",rma);
       //mandaphala calculation
      rmpa=3438*sin(11*rma/21);   //30*rma*22/(7*180)in radians
                            // NOTE: `11*rma/21` converts rma (in rashi,
                            //       1 rashi = 30 deg = pi/6 rad) to
                            //       radians for C's sin(), using the
                            //       traditional 22/7 approximation of pi
                            //       (pi/6 ~= (22/7)/6 = 22/42 = 11/21
                            //       EXACTLY) -- this is a correct radian
                            //       conversion, just via an ancient
                            //       rational pi approximation instead of
                            //       a precise value. `3438` is the
                            //       classical "trijya" (circle radius in
                            //       arcminutes, for a circle of
                            //       circumference 21600 arcminutes,
                            //       i.e. 360*60) -- so `rmpa` is the
                            //       equation-of-center correction
                            //       ("manda-phala"), in arcminutes on
                            //       that scale, for the Sun's orbital
                            //       eccentricity.
      rmp=rmpa*3/80;          // NOTE: rescale to a different unit
                            //       convention used by the rest of this
                            //       file.
      if(cnt==0)
      rmp1=rmp;  printf("rmp1=%lf",rmp1);
    //  printf("\nrmp=%lf",rmp);
      bp=(rmp/360)+rmp;        //rmp/6*60 convert to vikale
      printf("bp=%lf",bp);
       if(rmc<6)
      msr=rm-(bp/1800);        // NOTE: apply the correction, sign
      else                    //       depending on which half of the
      msr=rm+(bp/1800);        //       anomaly cycle we're in (before or
                            //       after the point of fastest motion).
                            //       `msr` = "manda-spashta ravi" = the
                            //       Sun's TRUE (corrected) longitude.
      if(cnt==0)msr1=msr;printf("msr1=%lf",msr1);
      printf("msr=%lf",msr);cnt++;
      rm=rm1+0.0328534;
      if(cnt==1)goto L1;       // NOTE: after the second pass (cnt==1),
                            //       fall through instead of looping
                            //       again.
      if(msr1>msr)
      rg=msr+12-msr1;
      else
      rg=msr-msr1;            // NOTE: `rg` = Ravi gati = the Sun's
                            //       instantaneous daily motion, from
                            //       differencing the two `msr` values
                            //       computed a small time-step apart.
      printf("rg=%lf",rg);
    //  printf("\nint=%ld",(long)integer);
      cnt=0;
      //calcn of chandra mahya

// ============================================================
// NOTE: SECTION 3 -- Chandra (Moon) madhya, uchcha (apogee),
//                    manda-phala -> sphuta position, Chandra gati
// ============================================================
cm=m*600/16393;//cm rashyadi   // NOTE: Moon's mean longitude, same
                            //       "uniform motion" starting point as
                            //       the Sun's rmr above, but with a much
                            //       faster daily-motion ratio
                            //       (600/16393 vs 31/11323), as expected
                            //       -- the Moon completes ~13.4 orbits
                            //       per year vs the Sun's 1.
cm_frac=modf(cm,&r);
//cmk=m/5256240;   //m*15/43802 kalaadi
cmk=(m*7)/36781200;//corrected factor printf("\n cmk=%lf",cmk);
                            // NOTE: comment says "corrected factor" --
                            //       i.e. the author revised this
                            //       constant from an earlier value
                            //       (still visible, commented out, on
                            //       the line above) without further
                            //       explanation of what was wrong with
                            //       the original or what the new value
                            //       is derived from.
cm=cm_frac*12-cmk;    //chakradi is converted rashyadi
cm1=cm=cm+1.303107;//-0.000833;deemed correction for tithinirnaya
                            // NOTE: another hand-fit epoch-offset
                            //       constant (again a DIFFERENT value
                            //       from the sibling files' 1.224157),
                            //       explicitly commented as being tuned
                            //       "for tithinirnaya" -- i.e. the
                            //       author was calibrating this against
                            //       observed/reference tithi timings,
                            //       not deriving it from first
                            //       principles.
if(cm>12)
cm=cm-12;
printf("\n cm=%lf",cm);
a1=rmp1/49200;  //rmp1*3/82 kala convtd to rashi
                            // NOTE: this is the Sun's manda-phala
                            //       correction applied to the Moon's
                            //       mean longitude too -- accounts for
                            //       the small effect of the Sun's
                            //       equation-of-center on the
                            //       Sun-referenced time system used to
                            //       evaluate the Moon's position.
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
a=rmp1/49200;  //rmp1*3/82 kala convtd to rashi
if(rmc<6)
scm=cm-a;
else
scm=cm+a;
if(scm>12)
scm=scm-12;
 printf("scm=%lf",scm);
 //calcn of chandra uchha
cu1=m/3232;// printf("\ncu1=%lf",cu1);
                            // NOTE: Moon's apogee ("uchcha") mean
                            //       longitude -- the point in the
                            //       Moon's orbit where it moves slowest
                            //       -- itself slowly precessing over
                            //       time (~8.85-year cycle in reality),
                            //       modeled here the same "mean motion +
                            //       correction" way as everything else.
cu1_frac=modf(cu1,&b);           //  printf("\ncu1_frac=%lf",cu1_frac);
//cuk=m/1383210;// printf("\ncuk=%lf",cuk); //m*40/30738 kala convtd to rashi
cuk=(m*7)/9338400;//corrected factor
cu1=cu1_frac*12-cuk;  //    printf("\ncu1=%lf",cu1);
cu1=cu1+2.009663;//-0.006935;deemed correction
                            // NOTE: yet another hand-fit constant,
                            //       different again from the sibling
                            //       files' 6.109093 -- same pattern as
                            //       above.
//printf("\ncu1=%lf",cu1);
if(cu1>12)
cu1=cu1-12;
cu=cu1+0.003712;
if(cu>12)
cu=cu-12;
L2:if(cu1>scm1)              // NOTE: same two-evaluations-for-a-
cmc1=scm1+12-cu1;            //       finite-difference pattern as L1
else                        //       above, this time for the Moon's
cmc1=scm1-cu1;              //       manda-phala / true longitude and
//printf("\ncmc1=%lf",cmc1); //       its daily motion (`cg`).
cma=check(cmc1);

 //mandaphala calculation
  cmpa=3438*sin(11*cma/21);   //30*rma*22/(7*180)in radians
                            // NOTE: same sine-table manda-phala
                            //       calculation as the Sun's, applied
                            //       to the Moon's anomaly (`cma`)
                            //       instead.
     cmp=cmpa*7/80;          // NOTE: different rescaling factor (7/80
                            //       here vs 3/80 for the Sun) --
                            //       reflects the Moon's larger orbital
                            //       eccentricity/equation-of-center
                            //       amplitude relative to the Sun's.
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
                            // NOTE: `cg` = Chandra gati = the Moon's
                            //       instantaneous daily motion, by the
                            //       same finite-difference method as
                            //       `rg` above.

// ============================================================
// NOTE: SECTION 4 -- Sayana (tropical) Sun, "chara khanda" correction,
//                    Ravi sputa / Chandra sputa (final apparent
//                    positions used for the tithi/nakshatra formulas)
// ============================================================
 ssr=msr1+ay; printf("\nssr=%lf",ssr);
                            // NOTE: `ssr` = sayana-spashta-ravi = the
                            //       Sun's TROPICAL true longitude
                            //       (sidereal true longitude + ayanamsha).
 if(ssr>12)
 ssrf=ssr=ssr-12;            // NOTE: wraps ssr into [0,12) BEFORE the
 else                        //       call to check() below. This wrap
 ssrf=ssr; printf("\nssrf=%lf",ssrf);  //  IS present here -- contrast
                            //       with the sibling program EKADHASI.C,
                            //       which omits exactly this wrap and,
                            //       confirmed by actually running it,
                            //       produces a negative, nonsensical
                            //       "chara khanda" as a result. This is
                            //       concrete evidence that EXP.C is a
                            //       later, bug-fixed descendant of that
                            //       code.
 ssr=check(ssr);
ssr=ssr*30;                  // NOTE: convert from rashi to degrees.
// printf("\nssr=%lf",ssr);
// NOTE: `chk` ("chara khanda") is a 9-segment piecewise-linear
// approximation of the "equation of time"-like correction that accounts
// for the varying rate at which the ecliptic rises relative to the
// celestial equator at a GIVEN LATITUDE (this is the oblique-ascension
// correction). Its coefficients (102, 99.9, 97.8, ... 11.9) are
// DIFFERENT from the sibling file TITHI-NI.C's (111, 108.7, 106.5, ...
// 13.0) for the exact same role -- strongly suggesting the two files
// were calibrated for two different geographic locations, since this
// table's shape depends on terrestrial latitude. Neither file states
// what location it assumes anywhere.
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
                            // NOTE: `chkr`/`chkc` scale the chara-khanda
                            //       correction by the Sun's/Moon's OWN
                            //       daily motion respectively -- this is
                            //       how a purely time-of-day correction
                            //       (chk) gets converted into an
                            //       equivalent LONGITUDE correction for
                            //       each body.
  printf("\nchkc=%lf",chkc);
  printf("\nchkr=%lf",chkr);
 if(ssrf<6)
{ rs=msr1-chkr/108000;
 cs=msc1-chkc/108000;}
 else
 { rs=msr1+chkr/108000;
 cs=msc1+chkc/108000;}       // NOTE: `rs` = Ravi sputa (Sun's final
                            //       apparent longitude), `cs` = Chandra
                            //       sputa (Moon's final apparent
                            //       longitude). Note that `cs` is NOT
                            //       re-wrapped into [0,12) here even
                            //       though it's built from `msc1 +/-` a
                            //       correction that could push it over
                            //       12 or under 0 -- see the "BUG" note
                            //       where `cs` is used below.
 printf("\nrs=%lf",rs);
 printf("\ncs=%lf",cs);

// ============================================================
// NOTE: SECTION 5 -- Tithi: elongation, tithi index, time remaining,
//                    upcoming tithi
// ============================================================
 if(rs>cs)
 vya=cs+12-rs;
 else
 vya=cs-rs;                  // NOTE: `vya` = elongation = Moon's
                            //       longitude minus Sun's longitude,
                            //       wrapped into [0,12) rashi (0-360
                            //       deg) -- correctly wrapped here,
                            //       unlike the `cs` bug below.
  printf("\nvya=%lf",vya);
 vyg=cg-rg;//in rashi         // NOTE: `vyg` = relative motion of Moon
                            //       vs Sun = the rate at which tithi
                            //       progresses.
  printf("\nvyg=%lf",vyg);
 x=vya*2.5;                  // NOTE: 1 tithi = 12 deg = 0.4 rashi of
                            //       elongation, and there are 30 tithis
                            //       in 12 rashi (360 deg), so
                            //       (elongation in rashi) * 2.5 =
                            //       number of tithis elapsed. This is
                            //       the key line: it converts a
                            //       continuous angle into a discrete
                            //       tithi count.
 x_frac=modf(x,&no_tithi);
 no_tithi+=1;                // NOTE: `no_tithi` = current tithi index,
                            //       1-30. `x_frac` = fraction of the
                            //       current tithi already elapsed.
// printf("\n\nno_tithi=%lf",no_tithi);
printf("\n\ntithi=%s",th_name[no_tithi-1]);
                            // NOTE: This is the line that prints
                            //       "s.ekadashi"/"k.ekadashi" (or any of
                            //       the other 28 tithi names) --
                            //       Ekadashi identification is entirely
                            //       generic, falling out of `no_tithi`
                            //       landing on index 11 or 26, with NO
                            //       Ekadashi-specific code anywhere in
                            //       this file.
 esh=0.4*(1.0-x_frac);//in  rashi
                            // NOTE: remaining angular distance (in
                            //       rashi) to the END of the current
                            //       tithi: 0.4 rashi is one full tithi's
                            //       width, times the fraction NOT yet
                            //       elapsed.
 tithi=esh*60/vyg; //printf("\ntithi=%lf",tithi);
                            // NOTE: convert remaining angular distance
                            //       to remaining TIME, using the
                            //       relative motion `vyg`: time =
                            //       distance / rate. Result is in
                            //       ghatika (60 ghatika = 1 day).
 tithi_fraction=modf(tithi,&integer);
      thig=ceil(tithi_fraction*60);// printf("\nthig=%lf",thig);//conversion to galige
                            // NOTE: sub-unit of ghatika: 1 ghatika = 60
                            //       vighatika ("galige").
      th=(long)tithi; //printf("\ntithi=%lf",th);
      if((esh+0.4)<vyg)
      {upthi=24/vyg;  //60*720/vyg in kale convtd to rashi
      rm_fraction=modf(upthi,&integer);
      upg=ceil(rm_fraction*60);printf("\nuparitithi=%s",th_name[no_tithi]);
      printf("\n\nuparitithi=%ld-%ld",(long)upthi,(long)upg);}
                            // NOTE: "uparitithi" = the NEXT tithi's
                            //       name and duration -- printed only
                            //       when the current tithi is short
                            //       enough that a second tithi boundary
                            //       falls within the same
                            //       elapsed-time window. This is
                            //       exactly the "tithi kshaya" situation
                            //       (a tithi too short to span a full
                            //       day) surfacing here as a
                            //       lookahead, though the program never
                            //       computes sunrise to know whether
                            //       that shortness actually matters for
                            //       a real civil day.
      printf("\ntithi=%ld-%ld",(long)th,(long)thig);

// ============================================================
// NOTE: SECTION 6 -- Nakshatra: Moon's longitude, index, time remaining
// ============================================================
      x=cs*2.25;             // NOTE: BUG: `cs` is used here directly,
                            //       without wrapping it into [0,12)
                            //       first (contrast with `vya` above,
                            //       which WAS correctly wrapped before
                            //       use). 360/27 = 13.333 deg per
                            //       nakshatra = (13.333/30) = 0.4444
                            //       rashi, and 1/0.4444 = 2.25, so
                            //       cs*2.25 = nakshatra count -- correct
                            //       in principle, but if `cs` has
                            //       drifted to 12 rashi or beyond (it is
                            //       built from `msc1 +/- chkc/108000`
                            //       above with no clamp), this produces
                            //       a nakshatra INDEX GREATER THAN 27.
                            //       CONFIRMED LIVE: running the sibling
                            //       file TITHI-NI.C (identical logic at
                            //       this point) produced cs=12.125991,
                            //       giving no_naks=28 below and reading
                            //       nk_name[27] -- one past the end of a
                            //       27-entry (indices 0-26) array. That
                            //       is undefined behavior in C (an
                            //       out-of-bounds read), and it visibly
                            //       corrupted that run's printed
                            //       nakshatra name. EXP.C has this exact
                            //       same unguarded `cs` here and would
                            //       hit the identical bug for any `m`
                            //       where `cs` drifts past 12 -- it
                            //       simply didn't happen to for m=702.
      x_frac=modf(x,&no_naks);
      no_naks+=1;
  printf("\n\nnakshatra=%s",nk_name[no_naks-1]);
      esh=4*(1-x_frac)/9;    // NOTE: 4/9 rashi = 360/27 deg = one
                            //       nakshatra's width; same
                            //       remaining-distance logic as the
                            //       tithi calculation above.
      nak=esh*60/cg;         // NOTE: convert remaining distance to
                            //       remaining time using the Moon's
                            //       daily motion `cg`.
       rm_fraction=modf(nak,&integer);
      nakg=ceil(rm_fraction*60);
      printf("\nnakshatra=%ld-%ld",(long)nak,(long)nakg);
       getch();

    }
```

## Summary: what's solid, what's broken, what's missing

**Solid and reusable** (verified by actually compiling and running this
file):
- The core idea -- elongation-based tithi identification, generic across
  all 30 tithis including both Ekadashis -- is structurally correct.
  Running the program across a sequence of consecutive `m` values (done
  with the sibling file `TITH_EXP.CPP`, which loops over `m`) shows the
  tithi index correctly advancing day to day.
- The ayanamsha calculation (the `jya[]` piecewise sine-table
  interpolation) is a genuine improvement over the sibling files, which
  hardcode a fixed linear ayanamsha drift rate that their own comment
  admits needs manual re-tuning "every ten years."
- The `ssr` mod-12 wrap before `check()` (Section 4) is present here and
  is missing in the sibling file `EKADHASI.C`, where its absence produces
  a confirmed, reproducible bad result (a negative chara-khanda value).

**Confirmed bugs, found by compiling and running the code, not just
reading it:**
1. **Nakshatra index out-of-bounds read.** `cs` is never wrapped into
   [0,12) before `x=cs*2.25` (Section 6). When `cs` drifts to ≥12, the
   resulting `no_naks` exceeds 27 and indexes past the end of the
   27-entry `nk_name` array -- undefined behavior, confirmed to
   reproducibly corrupt output when this exact code path was exercised.
2. **Portability**: `th_name[no_tithi-1]` and the other array lookups
   index with a `double` (`no_tithi`, `no_naks` are declared `double`).
   Turbo C tolerated this; standard C does not -- a modern compiler
   rejects it as a type error, and it must be cast to `int` to build at
   all today.

**Missing entirely** (confirmed by exhaustive search across every file in
both uploaded archives):
- No sunrise/sunset/moonrise/moonset calculation, or any location
  (latitude/longitude) input -- every "how much time is left" figure
  this program prints was compared against a sunrise time by hand,
  outside the program, by whoever ran it.
- No Gregorian-date-to-Ahargana conversion -- `m` must be hand-computed
  and the file recompiled per date.
- No sampradaya-specific (Smarta/Vaishnava) vrata decision rules --
  this program identifies which tithi is active, not which civil day a
  tradition observes as "Ekadashi."

See `docs/SPEC.md` and `panchanga/legacy/exp_c_reference.py` in this same
`tools/panchanga/` directory for the modernized replacement and a
bug-fixed, tested Python port of this exact file.
