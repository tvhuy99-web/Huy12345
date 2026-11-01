/* SPDX-License-Identifier: MIT. CI only: OpenAL/Sound3D ABI sentinels for the bounded audio IAT probe. */
#include <windows.h>
#include <stdint.h>
#ifdef BUILD_OPENAL
void __cdecl fixtureAlBufferData(unsigned int buffer,int format,const void *data,int size,int rate){
    (void)buffer;(void)format;(void)data;(void)size;(void)rate;
}
void __cdecl fixtureAlSourcePlay(unsigned int source){(void)source;}
#elif defined(BUILD_SOUND3D)
__declspec(dllimport) void __cdecl alBufferData(unsigned int,int,const void*,int,int);
__declspec(dllimport) void __cdecl alSourcePlay(unsigned int);
int __cdecl fixtureExerciseAudioHook(void){
    static const uint8_t data[16]={0,9,0,8,0,7,0,6,0,5,0,4,0,3,0,2};
    alBufferData(7,0x1101,data,(int)sizeof(data),22050);
    alSourcePlay(7);
    return 77;
}
#else
#error Select BUILD_OPENAL or BUILD_SOUND3D
#endif
