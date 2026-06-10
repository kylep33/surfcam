# surfcam
A setup for a machine to always have the pb surf cam up

1. first thing i did was go to https://hdontap.com/?utm_source=HDOnTap_Player&utm_medium=toolbar_logo&utm_campaign=customer_embed+pacificbeach_pacterrace-ingest01-hd1-CUST
2. when to f12 and then networking
3. searched m3u8 in the filter box
4. right clicked the blue link and clicked copy link.

5. Ran this command directly on the Orin AGX (which is already plugged into monitor:
   ```
   mpv --fullscreen --no-osc "https://live.hdontap.com/hls/hosb1/pacificbeach_pacterrace.stream/chunklist.m3u8?e=1780506661&eh=edge02.nginx.hdontap.com&t=ktza5dQS-uvq4deAih3eNQ"
   ```


   But here is how you use this script!

   1. Clone the repo.
   2. run python3 surfcam.py
