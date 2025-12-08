# 🎬 Sentiric Director Mode: Full Capability Test


**Kullanılan Varlıklar:**
```
# "Fenrir":   {"name": "M_TR_Heyecanli_Can", "lang": "tr", "gender": "M"},
# "Puck":     {"name": "M_TR_Enerjik_Mert",  "lang": "tr", "gender": "M"},
# "Kore":     {"name": "F_TR_Kurumsal_Ece",  "lang": "tr", "gender": "F"},
# "Leda":     {"name": "F_TR_Genc_Selin",    "lang": "tr", "gender": "F"},
# "Charon":   {"name": "M_TR_Tok_Kadir",     "lang": "tr", "gender": "M"},
# "Zephyr":   {"name": "F_TR_Parlak_Zeynep", "lang": "tr", "gender": "F"},
``` 

**Test edilabilecek Duygular:**
```
"tr": {
    "neutral": "Bu, Sentiric platformu için oluşturulmuş standart bir ses testidir. Sistem normal çalışıyor.",
    "happy": "Say cheerfully: İnanılmaz! Bu proje harika gidiyor, sonuçları görünce çok mutlu oldum!",
    "sad": "Say in a sad tone: Maalesef işler planladığımız gibi gitmedi, bu durum beni biraz üzüyor.",
    "angry": "Say angrily: Bu kabul edilemez! Derhal bu hatanın düzeltilmesini istiyorum!",
    "whisper": "Say in a spooky whisper: Şşt, sessiz ol. Bu çok gizli bir bilgi, kimsenin duymaması lazım."
},
"en": {
    "neutral": "This is a standard voice test for the Sentiric platform. Systems are operational.",
    "happy": "Say cheerfully: Wow! This is absolutely amazing news, I am so excited to see the results!",
    "sad": "Say in a sad tone: I am sorry to hear that, it is very unfortunate and disappointing.",
    "angry": "Say angrily: I cannot believe you did that! It is completely unacceptable!",
    "whisper": "Say in a spooky whisper: Hush, keep your voice down. This is a secret."
}
```

---


### 📝 SENARYO (Raw Script)

```text
---------------------------------------
Karşılama / Selamlama
---------------------------------------

F_TR_Genc_Selin (Neutral): Merhaba, ben Ece. Size nasıl yardımcı olabilirim?
M_TR_Heyecanli_Can (Neutral): Hoş geldiniz, ben Can. Nasıl destek olabilirim?
M_TR_Enerjik_Mert (Neutral): İyi günler! Ben Mert. Size hangi konuda yardımcı olabilirim?

---------------------------------------
Sorunu Anlama / Bilgi Alma
---------------------------------------

F_TR_Genc_Selin (Neutral): Durumu daha iyi anlayabilmem için birkaç bilgi rica edeceğim.
M_TR_Heyecanli_Can (Neutral): Yaşadığınız sorunu biraz daha detaylandırabilir misiniz?
M_TR_Enerjik_Mert (Neutral): Hemen kontrol ediyorum, lütfen bir dakika bekleyin.

---------------------------------------
Çözüm Sunma / Yönlendirme
---------------------------------------

F_TR_Genc_Selin (Neutral): Sizin için gerekli kontrolleri sağladım, şimdi yapmamız gereken adımları paylaşıyorum.
M_TR_Heyecanli_Can (Neutral): Bu konuda size şu şekilde yardımcı olabilirim…
M_TR_Enerjik_Mert (Neutral): Dilerseniz işlemi birlikte tamamlayabiliriz.

---------------------------------------
Bekletme / Zaman İsteme
---------------------------------------

F_TR_Genc_Selin (Neutral): Birazdan tekrar sizinle olacağım, lütfen hatta kalın.
M_TR_Heyecanli_Can (Neutral): Gerekli incelemeyi yapmam için kısa bir süre bekleteceğim.
M_TR_Enerjik_Mert (Neutral): İlgili birime danışmam gerekiyor, birkaç dakika içinde geri dönüş yapacağım.

---------------------------------------
Empati Kurma
---------------------------------------

F_TR_Genc_Selin (Neutral): Yaşadığınız durum için gerçekten üzgünüm.
M_TR_Heyecanli_Can (Neutral): Bu sürecin sizin için zor olduğunu anlıyorum, birlikte çözelim.
M_TR_Enerjik_Mert (Neutral): Endişenizi anlıyorum, size en hızlı şekilde yardımcı olacağım.

---------------------------------------
Kapanış / Teşekkür
---------------------------------------

F_TR_Genc_Selin (Neutral): Başka yardımcı olabileceğim bir konu var mı?
M_TR_Heyecanli_Can (Neutral): Bizi tercih ettiğiniz için teşekkür ederiz.
M_TR_Enerjik_Mert (Neutral): İyi günler dilerim, sağlıklı ve mutlu günler dilerim.


```

---
