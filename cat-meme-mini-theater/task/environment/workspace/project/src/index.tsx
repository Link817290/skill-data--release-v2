import React from 'react';
import {AbsoluteFill, Composition, registerRoot} from 'remotion';

const Film = () => <AbsoluteFill style={{backgroundColor: '#111827'}} />;
const Root = () => <Composition id="Film" component={Film} width={1920} height={1080} fps={30} durationInFrames={1200} />;
registerRoot(Root);
